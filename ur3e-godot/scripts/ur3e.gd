class_name UR3e
extends Node3D

# we need the *_holder nodes to essentially have some rotation offset
@onready var joints: Array[Marker3D] = [
	$v2/J0/J1,
	$v2/J0/J1/J2_holder/J2,
	$v2/J0/J1/J2_holder/J2/J3,
	$v2/J0/J1/J2_holder/J2/J3/J4_holder/J4,
	$v2/J0/J1/J2_holder/J2/J3/J4_holder/J4/J5,
	$v2/J0/J1/J2_holder/J2/J3/J4_holder/J4/J5/J6,
]

func rotate_joints(rotations: Array) -> void:
	assert(len(rotations) == len(joints), "Input count must match joint count")
	print(rotations)
	for i in rotations.size():
		match i:
			0, 4:
				joints[i].rotation.y = rotations[i]
			1, 2, 3, 5:
				joints[i].rotation.z = rotations[i]
