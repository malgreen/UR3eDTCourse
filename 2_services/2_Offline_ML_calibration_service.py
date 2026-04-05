
# Author: Nikan Mahdavi Tabatabaei

# Note that Generative AI helped slightly with the python coding in this service for convinience, but 
# not for the system-level planning, as the DT- and ML-engineering and both all of the general and detailed 
# system planning in this service was completely done by the author and not GAI at all. Even the 
# code-level planning was done by the author and not GAI. GAI was only sometimes used as a python coding 
# interface for our fully system-level and code-level pre-planned implementation, to get the python 
# syntaxes correct. 



# Here we will create an ML service for estimating the angular error between the mockup (PT) and the 
# emulator/DT (our model) using the near-uniform TCP pose space sampling from before, to achieve
# angular calibration through the "whole" TCP pose space. 





# Do the imports 

import numpy as np
import matplotlib.pyplot as plt
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
from tqdm import tqdm



# Configuration

INPUT_FILE = "1_dataset.csv"

INPUT_COLUMNS = [
    "q1_DT", "q2_DT", "q3_DT", "q4_DT", "q5_DT", "q6_DT"
]

TARGET_COLUMNS = [
    "q1_e", "q2_e", "q3_e", "q4_e", "q5_e", "q6_e"
]


TARGET_SCALE = 1.0
N_EPOCHS = 100
BATCH_SIZE = 4




# Dataset loading

df = pd.read_csv(INPUT_FILE)

X = df[INPUT_COLUMNS].to_numpy(dtype=float)
y = df[TARGET_COLUMNS].to_numpy(dtype=float)






# Data splitting into 70/10/20

X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.3, random_state=42
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=2/3, random_state=42
)






# Scaling the Input

x_scaler = StandardScaler()

X_train = x_scaler.fit_transform(X_train)
X_val = x_scaler.transform(X_val)
X_test = x_scaler.transform(X_test)
X_all = x_scaler.transform(X)




# The model

base_model = MLPRegressor(
    hidden_layer_sizes=(32, 32, 24, 16, 8),
    activation="relu",
    solver="adam",
    batch_size=BATCH_SIZE,
    learning_rate_init=0.001,
    alpha=0.001,
    max_iter=1,
    warm_start=True,
    random_state=42
)

model = base_model



# The training loop

train_r2 = []
val_r2 = []

train_loss = []
val_loss = []

epochs = []

for epoch in tqdm(range(1, N_EPOCHS + 1), desc="Training Epochs", colour="green"):

    model.fit(X_train, y_train)

    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)

    train_r2.append(r2_score(y_train, y_train_pred, multioutput="uniform_average"))
    val_r2.append(r2_score(y_val, y_val_pred, multioutput="uniform_average"))

    train_loss.append(mean_squared_error(y_train, y_train_pred))
    val_loss.append(mean_squared_error(y_val, y_val_pred))

    epochs.append(epoch)




# Testing 

y_test_pred = model.predict(X_test)

test_r2 = r2_score(y_test, y_test_pred, multioutput="uniform_average")
test_loss = mean_squared_error(y_test, y_test_pred)

print("\nTest Results (scaled)")
print(f"R2  : {test_r2:.6f}")
print(f"MSE : {test_loss:.6f}")



# Re-scaling the values back to the original radiens

y_test_rad = y_test / TARGET_SCALE
y_pred_rad = y_test_pred / TARGET_SCALE

test_mse_rad = mean_squared_error(y_test_rad, y_pred_rad) # MSE of: the error prediction vs the real error. 

y_test_rad = np.mean(y_test / TARGET_SCALE)
y_pred_rad = np.mean(y_test_pred / TARGET_SCALE)

print(f"\nTest MSE (radians): {test_mse_rad:.4e}")
print(f"\nPredicted Test Mean (radians): {y_pred_rad:.4e}")
print(f"\nActual Test Mean (radians): {y_test_rad:.4e}")
print("Test's R2 score:", test_r2)



# Save the model parameters for the next service

joblib.dump(
    {
        "model": model,
        "x_scaler": x_scaler,
        "target_scale": TARGET_SCALE,
        "input_columns": INPUT_COLUMNS,
        "target_columns": TARGET_COLUMNS
    },
    "2_MLP_model.joblib"
)



# Plot 1: R^2 over the course of the epochs

plt.figure()
plt.plot(epochs, train_r2, label="R2_Training")
plt.plot(epochs, val_r2, label="R2_Validation")
plt.axhline(test_r2, linestyle="--", label="R2_Test")

plt.xlabel("Epochs")
plt.ylabel("R2")
plt.title("R2 per epochs")
plt.legend()
plt.grid()
plt.show()




# Plot 2: Loss over the course of the epochs

plt.figure()
plt.plot(epochs, train_loss, label="Loss_Training")
plt.plot(epochs, val_loss, label="Loss_Validation")
plt.axhline(test_loss, linestyle="--", label="Loss_Test")

plt.xlabel("Epochs")
plt.ylabel("Loss_MSE")
plt.title("Loss per Epoch")
plt.legend()
plt.grid()
plt.show()


