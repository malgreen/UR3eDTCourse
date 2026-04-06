# Setup of the online communciations and the online calibration service. 

# Here we will setup the following communication paths:
# 1.   Listening and Subscription of this service to position-oriented control massages sent by 
#      us to the PT/teacher's mockup (and hence also the DT/our emulator), e.g., commands like 
#      moving the PT to a new Angle or TCP-pose. If detected, run the online calibration code
#      predicting the error for that command, and when done adding it to the DT model prediction. 
# 2.   Communication between the online calibration service and the DT/emulator for adding the corrections. 

# The Online calibration service will: 
# Take the command and predict the error for the given command, then add it to the DT/emulator 
# for better estimates. 


# In future this service could include adaptive tuning. 
