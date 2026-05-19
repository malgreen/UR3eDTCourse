
# Author: Nikan Mahdavi Tabatabaei

# Note Generative AI helped slightly with the python coding in this service for convinience, but 
# not for the system-level planning, as the DT-engineering and both all of the general and detailed 
# system planning in this service was completely done by the author and not GAI at all. Even the 
# code-level planning was done by the author and not GAI. GAI was only sometimes used as a python coding 
# interface for our fully system-level and code-level pre-planned implementation, to get the python 
# syntaxes correct. 



# Here we will create a near-uniform TCP pose space sampling service, which we will primary use for 
# sampling the TCP pose space of the mockup and our model, and use their angles in turn for a machine 
# learning-based error correction/calibration service. 

# So this file generates the angles (and the poses TCP corresponding for plotting) of a near-uniformly 
# sampled TCP pose space for both the PT and the DT. 

# We will also setup the communication to send commands and recieve outputs/messages from/to the 
# PT/teacher's mockup, in order to create the csv file. 




# Firstly activate the venv in the terminal in root folder. And remember to run docker as always! 
# Then, start the mockup/PT by openning a terminal in the root folder and running the command:
# python -m startup.start_ur3e_mockup



# Doing the Imports

import numpy as np
import matplotlib.pyplot as plt
import time
import pandas as pd
import roboticstoolbox as rtb

from threading import Thread, Lock, Event
from communication import protocol
from communication.rabbitmq import Rabbitmq






# Defining the UR3e DH model

link1 = rtb.RevoluteDH(d=0.15185, a=0, alpha=np.pi/2)
link2 = rtb.RevoluteDH(d=0, a=-0.24355, alpha=0)
link3 = rtb.RevoluteDH(d=0, a=-0.2132, alpha=0)
link4 = rtb.RevoluteDH(d=0.13105, a=0, alpha=np.pi/2)
link5 = rtb.RevoluteDH(d=0.08535, a=0, alpha=-np.pi/2)
link6 = rtb.RevoluteDH(d=0.0921, a=0, alpha=0)

ur3e_model = rtb.DHRobot(
    [link1, link2, link3, link4, link5, link6],
    name="UR3e Model"
)







# Starting the Configuration

NUM_SAMPLES = 1000
SAFE_Z_THRESHOLD = 0.075   # We set it as half of the first link's length, i.e., base link length, 
# (or d_0 in UR3e pircture from their wibsite), Which is just an approximation of bulk/diameter of 
# the links and joints, which might collide with the ground, being aware of the fact that the bulkniess 
# of the joints and links decreases as we move away from the base, making the threshold only more secure. 

SETTLE_TIME = 0.5
OUTPUT_FILE = "1_dataset.csv"

MOVE_TIMEOUT = 20.0
POSE_TIMEOUT = 10.0
Q_MATCH_TOL = 0.1   # in radians

# Joint limits
JOINT_LIMITS = [
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
]


# RabbitMQ states (shared)
sender_rmq = None
receiver_rmq = None
receiver_thread = None

latest_state = {
    "tcp_pose": None,
    "q_actual": None,
    "q_target": None,
    "robot_mode": None,
}

state_lock = Lock()
state_event = Event()






# Start Defining all the System Functions

def forward_kinematics(q):
    result = ur3e_model.fkine(q)

    xyz = result.t              # [x, y, z]
    rpy = result.rpy()          # [roll, pitch, yaw]

    return np.concatenate([xyz, rpy])


def angle_diff(a, b):
    return (a - b + np.pi) % (2*np.pi) - np.pi


def on_state_message_received(channel, method, properties, body):
    global latest_state

    if not isinstance(body, dict):
        return

    with state_lock:
        if "tcp_pose" in body:
            latest_state["tcp_pose"] = np.array(body["tcp_pose"], dtype=float)

        if "q_actual" in body:
            latest_state["q_actual"] = np.array(body["q_actual"], dtype=float)

        if "q_target" in body:
            latest_state["q_target"] = np.array(body["q_target"], dtype=float)

        if "robot_mode" in body:
            latest_state["robot_mode"] = body["robot_mode"]

    state_event.set()


def receiver():

    # A receiver thread for thestate messages of the PT.

    global receiver_rmq

    try:
        receiver_rmq = Rabbitmq(
            ip="localhost",
            port=5672,
            username="ur3e",
            password="ur3e",
            vhost="/",
            exchange="UR3E_AMQP",
            type="topic",
        )
        receiver_rmq.connect_to_server()

        receiver_rmq.subscribe(
            "robotarm.pt.state",
            on_state_message_received
        )

        receiver_rmq.start_consuming()

    except Exception as e:
        print(f"Receiver was stopped: {e}")


def start_robot_interface():
    # Here one receiver thread listening to PT state
    # And one sender RMQ connection for control messages

    global sender_rmq, receiver_thread

    state_event.clear()

    receiver_thread = Thread(target=receiver, daemon=True)
    receiver_thread.start()

    sender_rmq = Rabbitmq(
        ip="localhost",
        port=5672,
        username="ur3e",
        password="ur3e",
        vhost="/",
        exchange="UR3E_AMQP",
        type="topic",
    )
    sender_rmq.connect_to_server()

    # Waits until at least one of the state messages arrives
    if not state_event.wait(timeout=POSE_TIMEOUT):
        raise RuntimeError("No state messages received from the robot.")

    print("The robot is now interfaced")


def stop_robot_interface():
    # Close tboth he sender and the receiver RMQ connections.

    global sender_rmq, receiver_rmq

    if sender_rmq is not None:
        try:
            sender_rmq.close()
        except Exception as e:
            print(f"Warning closing sender RabbitMQ: {e}")
        sender_rmq = None

    if receiver_rmq is not None:
        try:
            receiver_rmq.close()
        except Exception as e:
            print(f"Warning closing receiver RabbitMQ: {e}")
        receiver_rmq = None



# If RMQ connection is lost:
def restart_robot_interface():
    global state_event

    print("RabbitMQ connection was lost. re-connecting...")

    while True:
        try:
            stop_robot_interface()
            time.sleep(2.0)
            state_event.clear()
            start_robot_interface()
            print("✓ Robot interface was reconnected")
            return
        except Exception as e:
            print(f"Re-connection failed: {e}")
            time.sleep(2.0)


def send_joint_command(q):
    # Send joint angles to PT mockup using the LOAD_PROGRAM and the PLAY

    # Here velocity and acceleration are omitted so the mockup uses its defaults from the startup.conf.

    if sender_rmq is None:
        raise RuntimeError("Sender RabbitMQ interface not started.")

    q = np.array(q, dtype=float).tolist()

    msg_load = {
        protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.LOAD_PROGRAM,
        protocol.CtrlMsgKeys.JOINT_POSITIONS: [q],
    }

    msg_play = {
        protocol.CtrlMsgKeys.TYPE: protocol.CtrlMsgFields.PLAY,
    }

    sender_rmq.send_message(
        routing_key=protocol.ROUTING_KEY_CTRL,
        message=msg_load
    )

    sender_rmq.send_message(
        routing_key=protocol.ROUTING_KEY_CTRL,
        message=msg_play
    )


def get_tcp_pose():
    # Reads latest TCP poses from the PT.

    # Returns the following: 
    # [x, y, z, roll, pitch, yaw]

    with state_lock:
        tcp_pose = latest_state["tcp_pose"]

    if tcp_pose is None:
        raise RuntimeError("No TCP poses ahve been received yet.")

    return np.array(tcp_pose, dtype=float)



def wait_until_target_reached(q_target, timeout=MOVE_TIMEOUT, tol=Q_MATCH_TOL):
    # Wait until (3 conditions) PT actual joints are close to target and robot is Idle, 
    # and also if the receiver thread is "alive".

    start = time.time()
    q_target = np.array(q_target, dtype=float)

    while time.time() - start < timeout:
        if receiver_thread is not None and not receiver_thread.is_alive():
            raise RuntimeError("Receiver thread just died.")

        with state_lock:
            q_actual = latest_state["q_actual"]
            robot_mode = latest_state["robot_mode"]

        if q_actual is not None:
            q_actual = np.array(q_actual, dtype=float)
            err = np.max(np.abs(angle_diff(q_actual, q_target)))

            if err < tol and robot_mode == "Idle":
                return True

        time.sleep(0.05)

    return False






# Sampling

def get_joint_sampling_config():
    # From our table:
    N = [14, 12, 8, 5, 3, 1]

    joint_ranges = []

    # only to get last joint to be at center, since there is actually only 1 place it can be:
    for (low, high), n in zip(JOINT_LIMITS, N):
        if n == 1:
            joint_ranges.append(np.array([(low + high) / 2]))
        else:
            joint_ranges.append(np.linspace(low, high, n))

    return joint_ranges


def structured_sampling():
    joint_ranges = get_joint_sampling_config()

    for q1 in joint_ranges[0]:
        for q2 in joint_ranges[1]:
            for q3 in joint_ranges[2]:
                for q4 in joint_ranges[3]:
                    for q5 in joint_ranges[4]:
                        for q6 in joint_ranges[5]:
                            yield np.array([q1, q2, q3, q4, q5, q6])



# introduce random joint selection within our samples, usefull when using number of samples < 20k, 
# in order to get a more uniform sampling. 
def random_sampling(num_samples):
    samples = list(structured_sampling())
    np.random.shuffle(samples)

    for q in samples[:num_samples]:
        yield q




# Checking

def is_safe(q):
    try:
        all_fk = ur3e_model.fkine_all(q)
        joint_positions = []

        # collect positions of link frames 1 to 6.
        for i in range(1, 7):
            p = all_fk[i].t
            joint_positions.append(p)

            if p[2] < SAFE_Z_THRESHOLD:
                return False

        # Reject configurations where non-neighboring (and non next-neighboring) joints get too close
        MIN_SELF_DIST = 0.02   # meters

        for i in range(len(joint_positions)):
            for j in range(i + 3, len(joint_positions)):   # skip neighboring and next-neighboring joints
                if np.linalg.norm(joint_positions[i] - joint_positions[j]) < MIN_SELF_DIST:
                    return False

        return True

    except Exception:
        return False







# Collecting Data

def collect_data():
    data = []
    count = 0

    print("Started the data computation and collection ...\n")

    start_robot_interface()

    try:
        for q in random_sampling(NUM_SAMPLES):

            if count >= NUM_SAMPLES:
                break

            if not is_safe(q):
                continue

            # DIGITAL TWIN
            tcp_dt = forward_kinematics(q)

            # PHYSICAL TWIN
            while True:
                try:
                    send_joint_command(q)

                    reached = wait_until_target_reached(q)
                    if not reached:
                        print(f"Skipping this sample: {count+1}. target was not reached in time.")
                        q_pt = None
                        break

                    time.sleep(SETTLE_TIME)

                    with state_lock:
                        q_pt = latest_state["q_actual"]


                    if q_pt is None:
                        print(f"Skipping this sample: {count+1}. none of the PT joint angles were received.")
                        q_pt = None
                        break

                    q_pt = np.array(q_pt, dtype=float)
                    break

                except Exception as e:
                    print(f"RMQ error: {e}")
                    restart_robot_interface()

            if q_pt is None:
                continue

            # STORE
            dq = angle_diff(q_pt, q)
            row = np.concatenate([q, q_pt, dq, tcp_dt])
            data.append(row)

            count += 1

            print(f"{count} out of {NUM_SAMPLES} samples are collected succesfully so far")

    finally:
        stop_robot_interface()

    print(f"\nFinished. Total Valid Combinations: {count}")
    return data







# Saving the Dataset

def save_dataset(data):
    columns = [
        "q1_DT", "q2_DT", "q3_DT", "q4_DT", "q5_DT", "q6_DT",
        "q1_PT", "q2_PT", "q3_PT", "q4_PT", "q5_PT", "q6_PT",
        "q1_e", "q2_e", "q3_e", "q4_e", "q5_e", "q6_e",
        "x_DT", "y_DT", "z_DT", "roll_DT", "pitch_DT", "yaw_DT"
    ]

    df = pd.DataFrame(data, columns=columns)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"Dataset was saved to {OUTPUT_FILE}")






# Visualize

def plot_3d_posespace(csv_file=OUTPUT_FILE):
    df = pd.read_csv(csv_file)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(df["x_DT"], df["y_DT"], df["z_DT"], s=2)

    ax.set_title("3D TCP pose space (DT)")
    ax.set_xlabel("X [meters]")
    ax.set_ylabel("Y [meters]")
    ax.set_zlabel("Z [meters]")

    plt.show()


def plot_concentration(csv_file=OUTPUT_FILE):
    df = pd.read_csv(csv_file)

    x = df["x_DT"]
    y = df["y_DT"]
    z = df["z_DT"]

    fig, axs = plt.subplots(1, 3, figsize=(15, 4))

    # XY
    axs[0].scatter(x, y, s=5)
    axs[0].set_title("XY Projection (DT TCP space 2D)")
    axs[0].set_xlabel("X [meters]")
    axs[0].set_ylabel("Y [meters]")
    axs[0].grid(True)

    # XZ
    axs[1].scatter(x, z, s=5)
    axs[1].set_title("XZ Projection (DT TCP space 2D)")
    axs[1].set_xlabel("X [meters]")
    axs[1].set_ylabel("Z [meters]")
    axs[1].grid(True)

    # YZ
    axs[2].scatter(y, z, s=5)
    axs[2].set_title("YZ Projection (DT TCP space 2D)")
    axs[2].set_xlabel("Y [meters]")
    axs[2].set_ylabel("Z [meters]")
    axs[2].grid(True)



    plt.tight_layout()
    plt.show()






# Finally, Running the Functions

if __name__ == "__main__":
    data = collect_data()
    save_dataset(data)

    # and for the visualization
    plot_3d_posespace()
    plot_concentration()

    