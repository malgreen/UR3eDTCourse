extends Node3D

@onready var ur3e: UR3e = $UR3e
@onready var rabbit_mq_listener: Node = $RabbitMQListener

func _ready() -> void:
    rabbit_mq_listener.connect("OnMessage", _on_message_received)


func _on_message_received(msg: String):
    var dict: Dictionary = JSON.parse_string(msg)
    if dict.get("q_actual") != null:
        ur3e.rotate_joints(dict["q_actual"])
        

## this is how the message looks:
# q_actual = rotations
# qd_actual = velocities
#{
#	"robot_mode": "Idle", 
#	"q_actual": [-5.091937626080412e-05, -1.5700026650473495, 1.5700010478123378, -1.570024065384959, -1.570001209062341, 3.7861117572591774e-05], 
#	"qd_actual": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 
#	"q_target": [0.0, -1.57, 1.57, -1.57, -1.57, 0.0], 
#	"timestamp": 2182.499999999174, 
#	"joint_max_speed": 60, 
#	"joint_max_acceleration": 80, 
#	"tcp_pose": [-0.2986799840661358, -0.13111885356249206, 0.3032406590875115, -1.5707069335491348, 0.0007706034434146294, 3.1407974963814573]
#}
