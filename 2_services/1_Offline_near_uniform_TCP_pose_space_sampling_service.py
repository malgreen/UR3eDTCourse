
# Here we will create a near-uniform TCP pose space sampling service, which we will primary use for 
# sampling the TCP pose space of the mockup and our model, which is in turn used for a machine 
# learning-based error correction/calibration service. 

# So this file generates the angles and the poses corresponding to a near-uniform TCP pose space 
# sampling for both the PT and the DT. 

# We will also setup the communication to send commands and recieve outputs/messages from/to the 
# PT/teacher's mockup, in order to create the csv file. 


# Here we will create a near-uniform TCP pose space sampling service, which we will primary use for
# sampling the TCP pose space of the mockup and our model, which is in turn used for a machine
# learning-based error correction/calibration service.

# So this file generates the angles and the poses corresponding to a near-uniform TCP pose space
# sampling for both the PT and the DT.

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






# Define the UR3e DH model

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







# Start Configuration

NUM_SAMPLES = 20160
SAFE_Z_THRESHOLD = 0.03
SETTLE_TIME = 0.5
OUTPUT_FILE = "dataset.csv"

MOVE_TIMEOUT = 15.0
POSE_TIMEOUT = 5.0
Q_MATCH_TOL = 0.03  # rad

# UR3e joint limits (adjust if needed)
JOINT_LIMITS = [
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
]

# RabbitMQ shared state
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






# Start Defining the System Functions

def forward_kinematics(q):
    result = ur3e_model.fkine(q)

    xyz = result.t              # [x, y, z]
    rpy = result.rpy()          # [roll, pitch, yaw]

    return np.concatenate([xyz, rpy])


def angle_diff(a, b):
    return (a - b + np.pi) % (2*np.pi) - np.pi


def on_state_message_received(channel, method, properties, body):
    """
    Receives PT state messages and stores latest values.

    Assumes body is a dict with:
        protocol.StateMsgKeys.TYPE
        protocol.StateMsgKeys.VALUE

    If your body prints differently, only this function needs adjusting.
    """
    global latest_state

    # Uncomment these 2 lines once if you want to inspect the exact message format:
    # print("STATE MESSAGE:")
    # print(body)

    if not isinstance(body, dict):
        return

    with state_lock:
        msg_type = body.get(protocol.StateMsgKeys.TYPE)
        value = body.get(protocol.StateMsgKeys.VALUE)

        if msg_type == protocol.StateMsgFields.TCP_POSE:
            latest_state["tcp_pose"] = np.array(value, dtype=float)

        elif msg_type == protocol.StateMsgFields.Q_ACTUAL:
            latest_state["q_actual"] = np.array(value, dtype=float)

        elif msg_type == protocol.StateMsgFields.Q_TARGET:
            latest_state["q_target"] = np.array(value, dtype=float)

        elif msg_type == protocol.StateMsgFields.ROBOT_MODE:
            latest_state["robot_mode"] = value

    state_event.set()


def receiver():
    """
    Dedicated receiver thread for PT state messages.
    """
    global receiver_rmq

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
        protocol.ROUTING_KEY_STATE,
        on_state_message_received
    )

    receiver_rmq.start_consuming()


def start_robot_interface():
    """
    Start:
    - one receiver thread listening to PT state
    - one sender RMQ connection for control messages
    """
    global sender_rmq, receiver_thread

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

    # Wait until at least one state message arrives
    if not state_event.wait(timeout=POSE_TIMEOUT):
        raise RuntimeError("No robot state messages received.")

    print("✓ Robot interface started")


def stop_robot_interface():
    """
    Close sender and receiver RMQ connections.
    """
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


def send_joint_command(q):
    """
    Send joint angles to PT mockup using:
    1) LOAD_PROGRAM
    2) PLAY

    Velocity and acceleration are omitted so the mockup uses
    its defaults from startup.conf.
    """
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
    """
    Read latest TCP pose from PT.
    Returns: [x, y, z, roll, pitch, yaw]
    """
    with state_lock:
        tcp_pose = latest_state["tcp_pose"]

    if tcp_pose is None:
        raise RuntimeError("No TCP pose received yet.")

    return np.array(tcp_pose, dtype=float)


def wait_until_target_reached(q_target, timeout=MOVE_TIMEOUT, tol=Q_MATCH_TOL):
    """
    Wait until PT actual joints are close to target.
    """
    start = time.time()
    q_target = np.array(q_target, dtype=float)

    while time.time() - start < timeout:
        with state_lock:
            q_actual = latest_state["q_actual"]

        if q_actual is not None:
            q_actual = np.array(q_actual, dtype=float)
            err = np.max(np.abs(angle_diff(q_actual, q_target)))
            if err < tol:
                return True

        time.sleep(0.05)

    return False






# Sampling

def get_joint_sampling_config():
    # From your table
    N = [14, 12, 8, 5, 3, 1]  # number of samples per joint

    joint_ranges = []

    for i, (low, high) in enumerate(JOINT_LIMITS):
        joint_ranges.append(np.linspace(low, high, N[i]))

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






# Checking

def is_safe(q):
    try:
        for i in range(1, 7):
            q_partial = np.zeros(6)
            q_partial[:i] = q[:i]

            partial_fk = ur3e_model.fkine(q_partial)
            z = partial_fk.t[2]

            if z < SAFE_Z_THRESHOLD:
                return False

        return True

    except Exception:
        return False







# Collecting Data

def collect_data():
    data = []
    count = 0

    print("Starting data collection...\n")

    start_robot_interface()

    try:
        for q in structured_sampling():

            if count >= NUM_SAMPLES:
                break

            if not is_safe(q):
                continue

            # DIGITAL TWIN
            tcp_dt = forward_kinematics(q)

            # PHYSICAL TWIN
            send_joint_command(q)

            reached = wait_until_target_reached(q)
            if not reached:
                print(f"Skipping sample {count+1}: target not reached in time.")
                continue

            time.sleep(SETTLE_TIME)
            tcp_pt = get_tcp_pose()

            # STORE
            row = np.concatenate([q, tcp_dt, tcp_pt])
            data.append(row)

            count += 1

            if count % 100 == 0:
                print(f"{count}/{NUM_SAMPLES} samples collected")

    finally:
        stop_robot_interface()

    print(f"\nDone. Total collected: {count}")
    return data







# Saving the Dataset

def save_dataset(data):
    new_data = []

    for row in data:
        tcp_dt = row[6:12]
        tcp_pt = row[12:18]

        # Position error
        pos_error = tcp_pt[0:3] - tcp_dt[0:3]

        # Orientation error (wrapped)
        rot_error = angle_diff(tcp_pt[3:6], tcp_dt[3:6])

        error = np.concatenate([pos_error, rot_error])

        # Append error to existing row
        new_row = np.concatenate([row, error])
        new_data.append(new_row)

    columns = [
        "q1", "q2", "q3", "q4", "q5", "q6",
        "x_dt", "y_dt", "z_dt", "roll_dt", "pitch_dt", "yaw_dt",
        "x_pt", "y_pt", "z_pt", "roll_pt", "pitch_pt", "yaw_pt",
        "dx", "dy", "dz", "droll", "dpitch", "dyaw"
    ]

    df = pd.DataFrame(new_data, columns=columns)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"Dataset saved to {OUTPUT_FILE}")






# Visualize

def plot_3d_workspace(csv_file=OUTPUT_FILE):
    df = pd.read_csv(csv_file)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(df["x_dt"], df["y_dt"], df["z_dt"], s=2)

    ax.set_title("3D TCP Workspace (DT)")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    plt.show()


def plot_heatmaps(csv_file=OUTPUT_FILE):
    df = pd.read_csv(csv_file)

    x = df["x_dt"]
    y = df["y_dt"]
    z = df["z_dt"]

    fig, axs = plt.subplots(1, 3, figsize=(15, 4))

    # XY heatmap
    h, xedges, yedges = np.histogram2d(x, y, bins=50)
    axs[0].imshow(
        h.T,
        origin='lower',
        aspect='auto',
        extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]]
    )
    axs[0].set_title("XY Density")
    axs[0].set_xlabel("X")
    axs[0].set_ylabel("Y")

    # XZ heatmap
    h, xedges, zedges = np.histogram2d(x, z, bins=50)
    axs[1].imshow(
        h.T,
        origin='lower',
        aspect='auto',
        extent=[xedges[0], xedges[-1], zedges[0], zedges[-1]]
    )
    axs[1].set_title("XZ Density")
    axs[1].set_xlabel("X")
    axs[1].set_ylabel("Z")

    # YZ heatmap
    h, yedges, zedges = np.histogram2d(y, z, bins=50)
    axs[2].imshow(
        h.T,
        origin='lower',
        aspect='auto',
        extent=[yedges[0], yedges[-1], zedges[0], zedges[-1]]
    )
    axs[2].set_title("YZ Density")
    axs[2].set_xlabel("Y")
    axs[2].set_ylabel("Z")

    plt.tight_layout()
    plt.show()






# Finally, Running the Functions

if __name__ == "__main__":
    data = collect_data()
    save_dataset(data)

    # Visualization
    plot_3d_workspace()
    plot_heatmaps()