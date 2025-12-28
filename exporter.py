import bpy
from mathutils import Euler, Matrix, Vector
from math import radians, degrees, pi
from decimal import *

from . import xsi

USE_FRAME_NAME_AS_MESH_NAME = True
ALLOW_MESH_WITH_NO_FACES = False
ALLOW_MESH_WITH_NO_MATERIAL = False
ALLOW_ROOT_LEVEL_ANIMS = True

KEYFRAME_PATHS = {"location", "rotation_euler", "rotation_quaternion", "scale"}
ALLOWED_SUB_OBJECTS_GLOBAL = {"MESH", "EMPTY", "ARMATURE"}

DEFAULT_MATERIAL = {
	"diffuse": (xsi.DEFAULT_DIFFUSE, tuple),
	"hardness": (xsi.DEFAULT_HARDNESS, float),
	"specular": (xsi.DEFAULT_SPECULAR, tuple),
	"ambient": (xsi.DEFAULT_AMBIENT, tuple),
	"emissive": (xsi.DEFAULT_EMISSIVE, tuple),
	"shading_type": (xsi.DEFAULT_SHADING_TYPE, int),
	"texture": (xsi.DEFAULT_TEXTURE, str),
	"width": (xsi.DEFAULT_WIDTH, int),
	"height": (xsi.DEFAULT_HEIGHT, int),
	"material_name": (xsi.DEFAULT_MATERIAL_NAME, str)
}

# centers mouse cursor to the Blender window
#def center_mouse_in_window():
#	region = bpy.context.region
	
#	window_cx = bpy.context.window.width // 2 + bpy.context.window.x
#	window_cy = bpy.context.window.height // 2 + bpy.context.window.y
	
#	return bpy.context.window.cursor_warp(window_cx, window_cy)

def ShowMessageBox(title_text="", message_text="", icon='INFO'):
	#center_mouse_in_window()
	
	def draw(self, context):
		self.layout.separator()
		self.layout.alignment = 'CENTER'
		self.layout.label(text="")
		self.layout.label(text=message_text, icon=icon)
		self.layout.separator()
	
	return bpy.context.window_manager.popup_menu(draw, title=title_text)

# Mesh for hardpoint objects
def generate_pointer_mesh(scale=0.05):
	xsimesh = xsi.Mesh()
	
	xsimesh.vertices = (
		(-scale, -scale, 0.0),
		(scale, -scale, 0.0),
		(-scale, scale, 0.0),
		(scale, scale, 0.0),
		(0.0, 0.0, 7.0 * scale)
	)
	
	xsimesh.normal_vertices = xsimesh.vertices
	xsimesh.faces = ((0, 2, 3, 1), (3, 2, 4), (0, 1, 4), (1, 3, 4), (2, 0, 4))
	xsimesh.normal_faces = xsimesh.faces
	xsimesh.face_materials = [xsi.Material(diffuse=(1.0, 1.0, 1.0))] * len(xsimesh.faces)
	
	return xsimesh

def generate_bone_mesh(bone, posebone):
	radius = bone.length*0.125
	base = bone.length*0.20
	tip = bone.length
	
	rgb = tuple(posebone.bone_group.colors.active)[0:3] if posebone.bone_group else xsi.DEFAULT_DIFFUSE[0:3]
	rgba = rgb + (0.80,)
	
	xsimesh = xsi.Mesh()
	
	xsimesh.vertices = (
		(-radius, base, -radius),
		(0.0, 0.0, 0.0),
		(radius, base, -radius),
		(-radius, base, radius),
		(radius, base, radius),
		(0.0, tip, 0.0)
	)
	
	xsimesh.faces = (
		(2, 4, 1),
		(1, 3, 0),
		(1, 4, 3),
		(2, 1, 0),
		(5, 3, 4),
		(5, 2, 0),
		(5, 0, 3),
		(5, 4, 2)
	)
	
	xsimesh.face_materials = [xsi.Material(diffuse=rgba)] * len(xsimesh.faces)
	
	xsimesh.normal_vertices = (
		(0.8, -0.6, 0),
		(0.8, -0.6, 0),
		(0.8, -0.6, 0),
		(-0.8, -0.6, 0),
		(-0.8, -0.6, 0),
		(-0.8, -0.6, 0),
		(0, -0.6, 0.8),
		(0, -0.6, 0.8),
		(0, -0.6, 0.8),
		(0, -0.6, -0.8),
		(0, -0.6, -0.8),
		(0, -0.6, -0.8),
		(0, 0.184289, 0.982872),
		(0, 0.184289, 0.982872),
		(0, 0.184289, 0.982872),
		(0, 0.184289, -0.982872),
		(0, 0.184289, -0.982872),
		(0, 0.184289, -0.982872),
		(-0.982872, 0.184289, 0),
		(-0.982872, 0.184289, 0),
		(-0.982872, 0.184289, 0),
		(0.982872, 0.184289, 0),
		(0.982872, 0.184289, 0),
		(0.982872, 0.184289, 0)
	)
	
	xsimesh.normal_faces = (
		(0, 1, 2),
		(3, 4, 5),
		(6, 7, 8),
		(9, 10, 11),
		(12, 13, 14),
		(15, 16, 17),
		(18, 19, 20),
		(21, 22, 23)
	)
	
	return xsimesh

def get_keyframes_filtered(action, keyframe_filter):
	filtered_points = {key: [] for key in keyframe_filter}
	key_start, key_end = tuple(action.frame_range)
	
	for fcurve in action.layers['Legacy Layer'].strips[0].channelbags[0].fcurves:
		if not fcurve.data_path in keyframe_filter:
			continue
		
		for point in fcurve.keyframe_points:
			pos = int(point.co[0])
			
			if point.co[0] in filtered_points[fcurve.data_path]:
				continue
			
			if pos >= key_start and pos <= key_end:
				filtered_points[fcurve.data_path].append(point)
	
	return filtered_points

# Returns dictionary of {Bone Name: [(Vert Index, Vert Weight)...]}
def get_vertex_weights(obj, group_names=None):
	vertex_weights = {}
	name_by_index = {}
	indices_used = []
	
	for vertex_group in obj.vertex_groups:
		if group_names == None or vertex_group.name in group_names:
			name_by_index[vertex_group.index] = vertex_group.name
			vertex_weights[vertex_group.name] = []
			indices_used.append(vertex_group.index)
	
	for vertex in obj.data.vertices:
		for group in vertex.groups:
			if group.group in indices_used:
				name = name_by_index[group.group]
				vertex_weights[name].append((vertex.index, group.weight * 100.0))
	
	return vertex_weights

def get_armature(bpy_obj):
	armature_mod = None
	for modifier in bpy_obj.modifiers:
		if modifier.type == "ARMATURE":
			if not armature_mod:
				armature_mod = modifier.object
			else:
				print("XSI WARNING: Multiple armature modifiers may cause unexpected results.")
				break
	
	return armature_mod

def obj_hierarchy_to_linear(bpy_objects):
	for bpy_obj in bpy_objects:
		for bpy_subobj in bpy_obj.children:
			if bpy_subobj.type in ALLOWED_SUB_OBJECTS_GLOBAL:
				yield bpy_subobj
			
			yield from obj_hierarchy_to_linear([bpy_subobj])

class Save:
	def __init__(self, operator, context, filepath="", **opt):
		self.depsgraph = context.evaluated_depsgraph_get()
		self.xsi_xsi = xsi.XSI()
		self.opt = opt
		
		original_keyframe_position = bpy.context.scene.frame_current
		
		#if opt["export_animations"] and original_keyframe_position != bpy.context.scene.frame_start:
		#	# This is so animated objects keyframe offset does not affect object's unanimated pose or matrix.
		#	# We'll set it back to original_keyframe_position later when we're done.
		#	bpy.context.scene.frame_set(bpy.context.scene.frame_start)
		
		if opt["export_mode"] == "ACTIVE_COLLECTION":
			objects = [obj for obj in bpy.context.view_layer.active_layer_collection.collection.objects if (obj.parent == None and not obj.hide_viewport)]
		
		elif opt["export_mode"] == "SELECTED_OBJECTS":
			objects = [obj for obj in bpy.data.objects if obj.select_get()]
		
		if len(objects) >= 2:
			print("XSI WARNING: Jedi Outcast/Jedi Academy do not support more than 1 root-level object:", ", ".join(obj.name for obj in objects))

		self.referenced_objects = objects + list(obj_hierarchy_to_linear(objects))
		self.enveloped_xsiframes = {}
		self.bone_name_to_xsiframe = {}
		
		for obj in objects:
			if obj.type in ALLOWED_SUB_OBJECTS_GLOBAL:
				self.xsi_xsi.frames += [self.object_to_xsiframe(obj, is_root_level=True)]
		
		# Envelopes for bones
		if opt["export_envelopes"]:
			for xsiframe, obj in self.enveloped_xsiframes.items():
				vertex_weights = get_vertex_weights(obj.evaluated_get(self.depsgraph), self.bone_name_to_xsiframe)
				
				for bone_name, xsibone in self.bone_name_to_xsiframe.items():
					if bone_name in vertex_weights:
						xsiframe.envelopes.append(xsi.Envelope(xsibone, vertex_weights[bone_name]))
					else:
						print("XSI WARNING: (Skin envelopes) Vertex group not found for bone:", bone_name)
		
		# Set keyframe position back, if changed during reading animation keyframes
		if bpy.context.scene.frame_current != original_keyframe_position:
			bpy.context.scene.frame_set(original_keyframe_position)
	
	def material_to_xsimaterial(self, material):
		mat = {}
		
		# Check material's custom attributes, these can be used to explicitly override material settings
		for key in DEFAULT_MATERIAL:
			default, value_type = DEFAULT_MATERIAL[key]
			if key in material: # if 'key' is in custom attributes of 'blender material object'
				mat[key] = value_type(material[key])
				# print("Using custom property %r with %r for material %r." % (key, mat[key], material.name))
			else:
				mat[key] = default
		
		if self.opt["export_jedi"]:
            # Use the material name
			mat["material_name"] = str(material.name)

		# Use the first texture in the node tree if applicable.
		if material.use_nodes and not mat["texture"]:
			for node in material.node_tree.nodes:
				if node.type == "TEX_IMAGE":
					# We want the filename + extension only
					path = str(node.image.filepath)
					filename = bpy.path.basename(path)
					mat["texture"] = filename
					mat["width"] = node.image.size[0]
					mat["height"] = node.image.size[1]
					break # Found an image texture.
				else:
					mat["texture"] = "noPic.pic"
		
		return xsi.Material(
			mat["diffuse"],
			mat["hardness"],
			mat["specular"],
			mat["ambient"],
			mat["emissive"],
			mat["shading_type"],
			mat["texture"],
			mat["width"],
			mat["height"],
			mat["material_name"]
		)

	def matrix_to_xsimatrix(self, local_matrix):
		return xsi.Matrix(*list(tuple(row) for row in tuple(local_matrix.transposed())))

	def matrix_to_xsi(self, matrix):
        # change the matrix to 'xsi style'
		row_y = -matrix.row[1].copy()
		row_z = matrix.row[2].copy()
		matrix.row[1] = row_z
		matrix.row[2] = row_y
		
		col_y = -matrix.col[1].copy()
		col_z = matrix.col[2].copy()
		matrix.col[1] = col_z
		matrix.col[2] = col_y

	def bone_mat_front_Y_to_X(self, matrix):
		# change the matrix rotation from front Y+ to front X+
		matrix[0][0], matrix[1][0], matrix[2][0], matrix[0][2], matrix[1][2], matrix[2][2] = matrix[0][2], matrix[1][2], matrix[2][2], - \
			matrix[0][0], -matrix[1][0], -matrix[2][0]
		
		col_y = matrix.col[1].copy()
		col_x = -matrix.col[0].copy()
		matrix.col[0] = col_y
		matrix.col[1] = col_x
		
		matrix[3][0], matrix[3][1] = matrix[3][1], -matrix[3][0]
	
	def object_to_xsiframe(self, obj, is_root_level=False):
		xsiframe = xsi.Frame(obj.name)
		xsiframe.mesh = None
		is_skinned = self.opt["export_envelopes"] and get_armature(obj) in self.referenced_objects
		
		# when we want to don't want to export meshes even though 
        # there's a model present in the scene
		if self.opt["export_mesh"]:
			ALLOWED_SUB_OBJECTS = ALLOWED_SUB_OBJECTS_GLOBAL
		else:
			ALLOWED_SUB_OBJECTS = {"EMPTY", "ARMATURE"}
		
		# 'zero out' the matrix for the scene root (usually 'model_root') object(s)
		if is_root_level and self.opt["zero_root_transforms"]:
			xsiframe.transform = self.matrix_to_xsimatrix(Matrix.Identity(4))
		else:
			if obj.parent is not None:
				matrix_local_parent = Matrix()
				matrix_local_parent @= Matrix(obj.parent.matrix_local)
				
				matrix_local = Matrix()
				matrix_local @= Matrix(obj.matrix_local)
				
				if self.opt["export_jedi"] and self.opt["export_gla_imp_skele"]:
					# change the 'front' from Y+ to X+
					self.bone_mat_front_Y_to_X(matrix_local_parent)
					self.bone_mat_front_Y_to_X(matrix_local)
                    
				mat_transform = matrix_local_parent.inverted() @ matrix_local
			else:
				matrix_local = Matrix()
				matrix_local @= Matrix(obj.matrix_local)
				
				if self.opt["export_jedi"] and self.opt["export_gla_imp_skele"]:
					# change the 'front' from Y+ to X+
					self.bone_mat_front_Y_to_X(matrix_local)
				
				mat_transform = matrix_local
			
			if self.opt["export_jedi"]:
				# zero out the matrix for the 'mesh_root' / 'skeleton_root' objects
				if obj.name == "mesh_root" or obj.name == "skeleton_root":
					xsiframe.transform = self.matrix_to_xsimatrix(Matrix.Identity(4))
				else:
					# convert the matrix to 'xsi style'
					self.matrix_to_xsi(mat_transform)
					
					# send the matrix to 'xsi.py' for writing...
					xsiframe.transform = self.matrix_to_xsimatrix(mat_transform)
			else:
				# convert the matrix to 'xsi style'
				self.matrix_to_xsi(mat_transform)
				
				xsiframe.transform = self.matrix_to_xsimatrix(mat_transform)
		
		if is_skinned:
			# just a copy of the 'FrameTransformMatrix'. send the matrix to 'xsi.py' for writing...
			xsiframe.pose = xsiframe.transform
		
		obj_eval = obj.evaluated_get(self.depsgraph)
		data = obj_eval.data
		
		scale = obj_eval.matrix_local.to_scale()
		
		if scale != Vector((1.0, 1.0, 1.0)):
			print("XSI WARNING: The scale for object %r = %r, which isn't supported by Jedi Outcast/Jedi Academy. Ensure all objects have the scale of 1.0 on all axis." % (obj.name, scale))
		
		if obj.type == "MESH" and not len(data.vertices) <= 0:
			if not ALLOW_MESH_WITH_NO_FACES and len(data.polygons) <= 0:
				print("XSI WARNING: Mesh object %r doesn't have any faces, skipping." % obj.name)
			
			else:
				if self.opt["export_mesh"]:
					xsiframe.mesh = self.mesh_to_xsimesh(data, xsiframe.name if USE_FRAME_NAME_AS_MESH_NAME else None)
					
					if is_skinned:
						# switch to armature REST position
						armature_obj = get_armature(obj)
						armature_obj.data.pose_position = 'REST'
						
                        # ensure the we're setting the skin weights at frame 0.
						bpy.context.scene.frame_set(bpy.context.scene.frame_start)
						
						self.enveloped_xsiframes[xsiframe] = obj_eval
		
		elif obj.type == "ARMATURE":
			for bone, posebone in zip(obj_eval.data.bones, obj_eval.pose.bones):
				if not bone.parent:
					xsiframe.frames += [self.bone_to_xsiframe(bone, posebone, obj_eval)]
		
		# All other supported blender types are treated as empty objects by default below.
		elif self.opt["generate_empty_mesh"]:
			xsiframe.mesh = generate_pointer_mesh()
			xsiframe.mesh.name = xsiframe.name
		
		if self.opt["export_animations"] and obj_eval.animation_data and obj_eval.animation_data.action:
			xsi_animations = list(self.animation_to_xsianim(obj_eval))
			
			if is_root_level and not ALLOW_ROOT_LEVEL_ANIMS:
				xsi_animations = []
			
			if xsi_animations:
				if is_root_level:
					print("XSI WARNING: Root-level object %r has animation data, and may not behave as expected in Jedi Outcast/Jedi Academy." % obj.name)
				
				xsiframe.animation_keys += list(self.animation_to_xsianim(obj_eval))
		
		for obj in obj.children:
			if obj.type in ALLOWED_SUB_OBJECTS:
				xsiframe.frames += [self.object_to_xsiframe(obj)]
		
		return xsiframe
	
	def animation_to_xsianim(self, obj):
		filtered_keyframes = get_keyframes_filtered(obj.animation_data.action, KEYFRAME_PATHS)
		
		# Convert the filtered keyframes to xsi keyframe animations
		for key_type, points in filtered_keyframes.items():
			if key_type == "scale":
				xsi_keyframe_type = 1
			elif key_type == "location":
				xsi_keyframe_type = 2
			else:
				if self.opt["export_euler"]:
					xsi_keyframe_type = 3
				else:
					xsi_keyframe_type = 0
            
			if not points:
				continue
			
			xsianim = xsi.AnimationKey(xsi_keyframe_type)
			
			for pos in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 1):
				bpy.context.scene.frame_set(pos)
                
				mat_obj = Matrix(obj.matrix_local)
				
				# convert the matrix to 'xsi style'
				self.matrix_to_xsi(mat_obj)
				
				# send the keys to 'xsi.py' for writing...
				if xsi_keyframe_type == 0:
					xsianim.add_key(pos, tuple(mat_obj.transposed().to_quaternion()))
				elif xsi_keyframe_type == 1:
					xsianim.add_key(pos, tuple(mat_obj.to_scale()))
				elif xsi_keyframe_type == 2:
					xsianim.add_key(pos, tuple(mat_obj.to_translation()))
				elif xsi_keyframe_type == 3:
					xsianim.add_key(pos, tuple([degrees(n) for n in mat_obj.to_euler()]))
			
			yield xsianim
	
	def bone_to_xsiframe(self, bone, posebone, armature):
		xsiframe = xsi.Frame(bone.name)
		xsiframe.is_bone = True
		self.bone_name_to_xsiframe[bone.name] = xsiframe
		
        # FrameTransformMatrix.
		# root bones are in world co-ordinates, and the child bones are relative to the parent
		if bone.parent is not None:
			matrix_local_parent = Matrix()
			matrix_local_parent @= Matrix(bone.parent.matrix_local)
			
			matrix_local = Matrix()
			matrix_local @= Matrix(bone.matrix_local)
            
			if self.opt["export_jedi"] and self.opt["export_gla_imp_skele"]:
				# change the 'front' from Y+ to X+
				self.bone_mat_front_Y_to_X(matrix_local_parent)
				self.bone_mat_front_Y_to_X(matrix_local)
				
			mat_transform = matrix_local_parent.inverted() @ matrix_local
			
			if self.opt["export_jedi"] and self.opt["export_facefix"]:
				# need to be compatible with Ravensoft's XSI 3 files, so
				# must apply face bone scaling of '1.087000' to match theirs...
				if bone.parent.name == "face":
					# change the scale for the child bones of 'face'
					mat_transform @= Matrix.Scale(1.087000, 4)
			
		else:
			matrix_local = Matrix()
			matrix_local @= Matrix(bone.matrix_local)
			
			if self.opt["export_jedi"] and self.opt["export_gla_imp_skele"]:
				# change the 'front' from Y+ to X+
				self.bone_mat_front_Y_to_X(matrix_local)
			
			mat_transform = matrix_local
			
		# convert the matrix to 'xsi style'
		self.matrix_to_xsi(mat_transform)
		
		xsiframe.transform = self.matrix_to_xsimatrix(mat_transform)
		
		# SI_FrameBasePoseMatrix
        # just a copy of the 'FrameTransformMatrix'. send the matrix to 'xsi.py' for writing...
		xsiframe.pose = xsiframe.transform
		
		for child_bone, child_posebone in zip(bone.children, posebone.children):
			xsiframe.frames += [self.bone_to_xsiframe(child_bone, child_posebone, armature)]
		
		if self.opt["generate_bone_mesh"]:
			xsiframe.mesh = generate_bone_mesh(bone, posebone)
			xsiframe.mesh.name = bone.name
		
		if self.opt["export_animations"]:
			if armature.animation_data and armature.animation_data.action:
				# Switch to armature POSE position
				armature.data.pose_position = 'POSE'
				
				xsiframe.animation_keys += list(self.bone_animation_to_xsianim(bone, posebone, armature))
		
		return xsiframe
	
	def bone_animation_to_xsianim(self, bone, posebone, armature):
		keyframe_filter = ["pose.bones[\"%s\"].%s" % (bone.name, path) for path in KEYFRAME_PATHS]
		filtered_keyframes = get_keyframes_filtered(armature.animation_data.action, keyframe_filter)
		
		# convert the filtered keyframes to xsi keyframe animations
		location_path_name = "pose.bones[\"%s\"].location" % bone.name
		scale_path_name = "pose.bones[\"%s\"].scale" % bone.name
        
		for key_type, points in filtered_keyframes.items():
			if key_type == scale_path_name:
				xsi_keyframe_type = 1
			elif key_type == location_path_name:
				xsi_keyframe_type = 2
			else:
				if self.opt["export_euler"]:
					xsi_keyframe_type = 3
				else:
					xsi_keyframe_type = 0
			
			if not points:
				continue
			
			xsianim = xsi.AnimationKey(xsi_keyframe_type)
			
			for pos in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 1):
				bpy.context.scene.frame_set(pos)
				
				if posebone.parent is not None:
					matrix_local_parent = Matrix()
					matrix_local_parent @= Matrix(posebone.parent.matrix)
					
					matrix_local = Matrix()
					matrix_local @= Matrix(posebone.matrix)
                    
					if self.opt["export_jedi"] and self.opt["export_gla_imp_skele"]:
						# change the 'front' from Y+ to X+
						self.bone_mat_front_Y_to_X(matrix_local_parent)
						self.bone_mat_front_Y_to_X(matrix_local)
					
					mat_posebone = matrix_local_parent.inverted() @ matrix_local
					
					if self.opt["export_jedi"] and self.opt["export_facefix"]:
						# need to be compatible with Ravensoft's XSI 3 files, so
						# must apply face bone scaling of '1.087000' to match theirs...
						if posebone.parent.name == "face":
							# change the scale for the child bones of 'face'
							mat_posebone @= Matrix.Scale(1.087000, 4)
					
				else:
					matrix_local = Matrix()
					matrix_local @= Matrix(posebone.matrix)
					
					if self.opt["export_jedi"] and self.opt["export_gla_imp_skele"]:
						# change the 'front' from Y+ to X+
						self.bone_mat_front_Y_to_X(matrix_local)
					
					mat_posebone = matrix_local
				
				# convert the matrix to 'xsi style'
				self.matrix_to_xsi(mat_posebone)
				
				# send the keys to 'xsi.py' for writing...
				if xsi_keyframe_type == 0:
					xsianim.add_key(pos, tuple(mat_posebone.transposed().to_quaternion()))
				elif xsi_keyframe_type == 1:
					xsianim.add_key(pos, tuple(mat_posebone.to_scale()))
				elif xsi_keyframe_type == 2:
					xsianim.add_key(pos, tuple(mat_posebone.to_translation()))				
				elif xsi_keyframe_type == 3:
					xsianim.add_key(pos, tuple([degrees(n) for n in mat_posebone.to_euler()]))
			
			yield xsianim
	
	def mesh_to_xsimesh(self, data, name=None):
		xsimesh = xsi.Mesh(name if name else data.name)
		
		xsimaterials = []
		
		if self.opt["export_mesh_materials"]:
			for material in data.materials:
				xsimaterials += [self.material_to_xsimaterial(material)]
		
		for vertex in data.vertices:
			# change the vertex positions to 'xsi style'
			vert_Y = vertex.co.y * -1
			vertex.co.y = vertex.co.z
			vertex.co.z = vert_Y
			
			xsimesh.vertices += [tuple(vertex.co.xyz)]				
                
		
		for polygon in data.polygons:
			xsimesh.faces += [tuple(polygon.vertices)]
		
		if xsimaterials:
			for polygon in data.polygons:
				xsimesh.face_materials += [xsimaterials[polygon.material_index]]
		
		elif not ALLOW_MESH_WITH_NO_MATERIAL:
			print("XSI WARNING: Mesh %r doesn't have any materials, adding a default material instead." % name)
			
			xsimesh.face_materials = [xsi.Material()] # Default material
		
		active_uv_layer = data.uv_layers.active
		uv_layer = active_uv_layer.data if active_uv_layer else None
		active_color_layer = data.vertex_colors.active
		color_layer = active_color_layer.data if active_color_layer else None
		
		# Normals and mesh loop faces (loop indices shared for uv and vert colors)
		for polygon in data.polygons:
			for loop_index in polygon.loop_indices:
				xsimesh.normal_vertices += [tuple(data.loops[loop_index].normal)]
			
			xsimesh.normal_faces += [tuple(polygon.loop_indices)]
		
		if uv_layer and self.opt["export_mesh_uvmap"]:
			for poly in data.polygons:
				for loop_index in poly.loop_indices:
					xsimesh.uv_vertices += [tuple(uv_layer[loop_index].uv)]
			
			xsimesh.uv_faces = xsimesh.normal_faces
		
		if color_layer and self.opt["export_mesh_vertcolor"]:
			for poly in data.polygons:
				for loop_index in poly.loop_indices:
					xsimesh.vertex_colors += [tuple(color_layer[loop_index].color)]
			
			xsimesh.vertex_color_faces = xsimesh.normal_faces
		
		return xsimesh

def save(operator, context, filepath="", **opt):
	Save(operator, context, filepath=filepath, **opt).xsi_xsi.write(filepath=filepath)
	ShowMessageBox("Softimage XSI Exporter", "Exported successfully!", 'CHECKMARK')
	return {"FINISHED"}
