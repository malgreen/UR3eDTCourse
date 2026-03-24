
# Here we will create a near-uniform TCP pose space sampling service, which we will primary use for 
# sampling the TCP pose space of the mockup and our model, which is in turn used for a machine 
# learning-based error correction/calibration service. 

# So this file generates the angles and the poses corresponding to a near-uniform TCP pose space 
# sampling for both the PT and the DT. 




# Doing the Imports

import numpy as np
import matplotlib.pyplot as plt
import time
import pandas as pd
import roboticstoolbox as rtb








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

NUM_SAMPLES = 3000
SAFE_Z_THRESHOLD = 0.02
SETTLE_TIME = 0.5
OUTPUT_FILE = "dataset.csv"

# UR3e joint limits (adjust if needed)
JOINT_LIMITS = [
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
    (-2*np.pi, 2*np.pi),
]







# Start Defining the System Functions

def forward_kinematics(q):
    result = ur3e_model.fkine(q)

    xyz = result.t              # [x, y, z]
    rpy = result.rpy()          # [roll, pitch, yaw]

    return np.concatenate([xyz, rpy])


def send_joint_command(q):
    """
    Send joint angles to PT mockup
    """
    # TODO: implement based on your setup
    pass


def get_tcp_pose():
    """
    Read TCP pose from PT
    Returns: [x, y, z, roll, pitch, yaw]
    """
    # TODO: implement based on your setup
    return np.zeros(6)








# Sampling

def sample_joint_angles():
    return np.array([
        np.random.uniform(low, high)
        for low, high in JOINT_LIMITS
    ])









# Checking

def is_safe(q):
    try:
        tcp = forward_kinematics(q)
        return tcp[2] > SAFE_Z_THRESHOLD
    except:
        return False









# Collecting Data

def collect_data():
    data = []
    count = 0
    attempts = 0

    print("Starting data collection...\n")

    while count < NUM_SAMPLES:
        attempts += 1

        q = sample_joint_angles()

        if not is_safe(q):
            continue

        # DIGITAL TWIN
        tcp_dt = forward_kinematics(q)

        # PHYSICAL TWIN
        send_joint_command(q)
        time.sleep(SETTLE_TIME)
        tcp_pt = get_tcp_pose()

        # STORE
        row = np.concatenate([q, tcp_dt, tcp_pt])
        data.append(row)

        count += 1

        if count % 100 == 0:
            print(f"{count}/{NUM_SAMPLES} samples collected")

    print(f"\nDone. Total attempts: {attempts}")
    return data










# Saving the Dataset

def angle_diff(a, b):
    return (a - b + np.pi) % (2*np.pi) - np.pi



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
        "q1","q2","q3","q4","q5","q6",
        "x_dt","y_dt","z_dt","roll_dt","pitch_dt","yaw_dt",
        "x_pt","y_pt","z_pt","roll_pt","pitch_pt","yaw_pt",
        "dx","dy","dz","droll","dpitch","dyaw"
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
    axs[0].imshow(h.T, origin='lower', aspect='auto',
                  extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]])
    axs[0].set_title("XY Density")
    axs[0].set_xlabel("X")
    axs[0].set_ylabel("Y")

    # XZ heatmap
    h, xedges, zedges = np.histogram2d(x, z, bins=50)
    axs[1].imshow(h.T, origin='lower', aspect='auto',
                  extent=[xedges[0], xedges[-1], zedges[0], zedges[-1]])
    axs[1].set_title("XZ Density")
    axs[1].set_xlabel("X")
    axs[1].set_ylabel("Z")

    # YZ heatmap
    h, yedges, zedges = np.histogram2d(y, z, bins=50)
    axs[2].imshow(h.T, origin='lower', aspect='auto',
                  extent=[yedges[0], yedges[-1], zedges[0], zedges[-1]])
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