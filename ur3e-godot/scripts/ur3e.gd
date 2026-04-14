extends Node3D

@onready var joints: Array[Marker3D] = [
	$v2/J0/J1, 
	$v2/J0/J1/J2, 
	$v2/J0/J1/J2/J3, 
	$v2/J0/J1/J2/J3/J4,
	$v2/J0/J1/J2/J3/J4/J5,
	$v2/J0/J1/J2/J3/J4/J5/J6,
]

func rotate_joints(rotations: Array) -> void:
	assert(len(rotations) == len(joints), "Input count must match joint count")
	print(rotations)
	#for i in rotations.size:
		#joints[i].global_rotate(rotations[i])
		
	

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass
