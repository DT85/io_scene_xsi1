"""This module provides Blender to XSI utilities, including a writer for XSI 1.0 files."""
VERSION = 1.0

# No print calls will be made by the module if this is False
ALLOW_PRINT = True

DEFAULT_DIFFUSE = (0.7, 0.7, 0.7, 1.0)
DEFAULT_SPECULAR = (0.35, 0.35, 0.35)
DEFAULT_EMISSIVE = (0.0, 0.0, 0.0)
DEFAULT_AMBIENT = (0.5, 0.5, 0.5)
DEFAULT_HARDNESS = 200.0
DEFAULT_SHADING_TYPE = 2
DEFAULT_TEXTURE = None

DEFAULT_XSI_NAME = "<XSI ROOT>"

RENAME_DUPLICATE_NAMED_FRAMES = True
DUPLICATE_FRAME_NOEXCEPT = False

import bpy
from datetime import datetime

class DuplicateFrame(Exception): pass

# XSI & Frame inherit from this internal class
class _FrameContainer:
	def __init__(self):
		self.xsi = self
		self.frames = []
	
	def add_frame(self, name):
		if name in self.xsi.frame_table and not DUPLICATE_FRAME_NOEXCEPT:
			raise DuplicateFrame("Duplicate Frame %r" % name)
		
		frame = Frame(name)
		frame.parent = self if not self is self.xsi else None # XSI container itself is not a parent
		frame.xsi = self.xsi
		
		self.xsi.frame_table[name] = frame
		self.frames.append(frame)
		
		return frame
	
	def get_all_frames(self):
		frames = []
		for frame in self.frames:
			yield frame
			yield from frame.get_all_frames()
	
	def find_frame(self, name):
		for frame in self.get_all_frames():
			if frame.name == name:
				return frame
	
	def get_animated_frames(self):
		for frame in self.get_all_frames():
			if frame.animation_keys:
				yield frame
	
	def get_skinned_frames(self):
		for frame in self.get_all_frames():
			if frame.envelopes:
				yield frame
	
	def get_bone_frames(self):
		for frame in self.get_all_frames():
			if frame.is_bone:
				yield frame
	
	def get_all_meshes(self):
		for frame in self.get_all_frames():
			if frame.mesh:
				yield frame.mesh
	
	def get_envelope_count(self):
		"""Returns total amount of envelopes in each frame."""
		return sum((len(f.envelopes) for f in self.get_skinned_frames()))

class XSI(_FrameContainer):
	def __init__(self, filepath=None):
		self.frame_table = {}
		self.lights = []
		self.cameras = []
		self.frames = []
		self.xsi = self
		
		self.name = filepath if filepath else DEFAULT_XSI_NAME
		
		if filepath:
			self.read(filepath)
	
	def read(self, filepath, re_skip=None):
		with open(filepath, "r") as f:
			self.name = filepath
			Reader(f, bz2xsi_xsi=self, re_skip=re_skip, log_name=self.name)
	
	def write(self, filepath):
		with open(filepath, "w") as f:
			Writer(self, f)
	
	def is_skinned(self):
		return len(list(self.get_skinned_frames())) >= 1
	
	def is_animated(self):
		return len(list(self.get_animated_frames())) >= 1
	
	# String representation will result in XML output
	def __str__(self):
		return "%s<XSI>%s%s</XSI>" % (
			"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\" ?>\n",
			"".join(map(str, self.lights)),
			"".join(map(str, self.frames)),
		)

class PointLight:
	def __init__(self, name, rgb=None, location_xyz=None):
		self.name = name
		self.rgb = rgb if rgb else (1.0, 1.0, 1.0)
		
		if not location_xyz:
			location_xyz = (0.0, 0.0, 0.0)
		
		self.transform = Matrix(posit=(*location_xyz, 1.0))
	
	def __str__(self):
		return "<PointLight>%s (%f, %f, %f)</PointLight>" % (self.name, *self.rgb)

class Camera:
	def __init__(self, name, location_xyz=None, look_at_xyz=None, roll=0.0, near_plane=0.001, far_plane=1000.0):
		self.name = name
		self.roll = roll
		self.near_plane = near_plane
		self.far_plane = far_plane
		
		if not location_xyz:
			location_xyz = (0.0, 0.0, 0.0)
		
		if not look_at_xyz:
			look_at_xyz = (0.0, 0.0, 0.0)
		
		self.transform = Matrix(posit=(*location_xyz, 1.0))
		self.target = Matrix(posit=(*look_at_xyz, 1.0))
	
	def __str__(self):
		return "<Camera>%s</Camera>" % self.name

class Frame(_FrameContainer):
	def __init__(self, name):
		self.name = name
		self.is_bone = False
		
		self.transform = None
		self.pose = None
		self.mesh = None
		
		self.parent = None
		self.frames = []
		self.animation_keys = []
		
		# About envelopes:
		# Frames (meshes) which are NOT bones contain envelopes.
		# Frames which ARE bones do NOT contain envelopes, but are referenced BY envelopes.
		self.envelopes = []
	
	def __str__(self):
		return "<Frame>%s%s%s%s%s%s%s</Frame>" % (
			self.name,
			str(self.transform),
			str(self.pose),
			str(self.mesh),
			"".join(map(str, self.frames)),
			"".join(map(str, self.animation_keys)),
			"".join(map(str, self.envelopes)),
		)
	
	def get_animation_frame_range(self):
		start = end = None
		for animkey in self.animation_keys:
			for keyframe, vector in animkey.keys:
				if start == None or keyframe < start:
					start = keyframe
				if end == None or keyframe > end:
					end = keyframe
		return start, end
	
	def get_chained_name(self, delimiter=" -> "):
		frm, chain = self, []
		
		while frm:
			chain += [frm.name]
			frm = frm.parent
		
		return delimiter.join(reversed(chain))
	
	def add_animationkey(self, *args):
		self.animation_keys.append(AnimationKey(*args))
		return self.animation_keys[-1]
	
	def add_envelope(self, *args):
		self.envelopes.append(Envelope(*args))
		return self.envelopes[-1]

class Matrix:
	def __init__(self, right=None, up=None, front=None, posit=None):
		self.right = right #if right else (1.0, 0.0, 0.0, 0.0)
		self.up    = up    #if up    else (0.0, 1.0, 0.0, 0.0)
		self.front = front #if front else (0.0, 0.0, 1.0, 0.0)
		self.posit = posit #if posit else (0.0, 0.0, 0.0, 1.0)
	
	def __str__(self):
		return "<Matrix>(x=%f y=%f z=%f)</Matrix>" % tuple(self.posit[0:3])
	
	def to_list(self):
		return [list(self.right), list(self.up), list(self.front), list(self.posit)]

class Mesh:
	def __init__(self, name=None):
		self.name=name
		
		self.vertices = []
		self.faces = []
		
		self.normal_vertices = []
		self.normal_faces = []
		
		self.uv_vertices = []
		self.uv_faces = []
		
		self.face_materials = []
		
		self.vertex_colors = []
		self.vertex_color_faces = []
	
	def __str__(self):
		def XML(name, vertices, faces):
			if vertices or faces:
				return "<%s>%d Vertices %d Faces</%s>" % (
					name,
					len(vertices),
					len(faces),
					name
				)
			else:
				return ""
		
		indices, materials = self.get_material_indices()
		
		return "<Mesh>%d Vertices %d Faces%s%s%s%s</Mesh>" % (
			len(self.vertices),
			len(self.faces),
			"".join(map(str, materials)),
			XML("Normals", self.normal_vertices, self.normal_faces),
			XML("UV-Map", self.uv_vertices, self.uv_faces),
			XML("Vertex-Colors", self.vertex_colors, self.vertex_color_faces)
		)
	
	def get_material_indices(self):
		materials = []
		indices = []
		for material in self.face_materials:
			if not material in materials:
				materials += [material]
			
			indices += [materials.index(material)]
		
		return indices, materials

class Material:
	def __init__(self,
				diffuse=None, hardness=DEFAULT_HARDNESS, specular=None,
				ambient=None, emissive=None, shading_type=DEFAULT_SHADING_TYPE,
				texture=None
			):
		self.diffuse  = diffuse  if diffuse  else list(DEFAULT_DIFFUSE)
		self.specular = specular if specular else list(DEFAULT_SPECULAR)
		self.emissive = emissive if emissive else list(DEFAULT_EMISSIVE)
		self.ambient  = ambient  if ambient  else list(DEFAULT_AMBIENT)
		
		self.hardness = hardness
		self.shading_type = shading_type
		self.texture = texture
		
		if len(self.diffuse) == 3:
			self.diffuse += (1.0,) # Append alpha channel
		
		elif len(self.diffuse) != 4:
			raise TypeError("Material Diffuse color must be RGB or RGBA.")
		
		if len(self.specular) != 3:
			raise TypeError("Material Specular color must be RGB.")
		
		if len(self.emissive) != 3:
			raise TypeError("Material Emissive color must be RGB.")
		
		if len(self.ambient) != 3:
			raise TypeError("Material Ambient color must be RGB.")
	
	def __str__(self):
		return "<Material>%r (%f, %f, %f, %f)</Material>" % (str(self.texture), *self.diffuse)
	
	def __eq__(self, other):
		return (
			self.texture == other.texture
			and self.diffuse      == other.diffuse
			and self.hardness     == other.hardness
			and self.specular     == other.specular
			and self.ambient      == other.ambient
			and self.emissive     == other.emissive
			and self.shading_type == other.shading_type
		)
	
	def __nq__(self, other):
		return not self.__eq__(other)

class AnimationKey:
	TYPE_SIZE = (
		4, # 0: WXYZ Quaternion Rotation
		3, # 1: XYZ Scale
		3, # 2: XYZ Translate
		3  # 3: XYZ Euler Rotation
	)
	
	def __str__(self):
		return "<AnimationKey>%d:%d Keys</AnimationKey>" % (self.key_type, len(self.keys))
	
	def __init__(self, key_type):
		if not key_type in range(4):
			raise ValueError("Invalid Animation Key Type %d" % key_type)
		
		self.key_type = key_type
		self.keys = []
		self.vector_size = __class__.TYPE_SIZE[self.key_type]
	
	def add_key(self, keyframe, vector):
		if len(vector) != self.vector_size:
			raise ValueError("Incorrect Vector Size")
		
		self.keys.append((keyframe, vector))
		
		return self.keys[-1]

class Envelope:
	def __init__(self, bone, vertices=None):
		self.bone = bone # bone is a Frame object which is the bone this envelope refers to.
		self.vertices = vertices if vertices else []
	
	def __str__(self):
		return "<Envelope>Bone %s</Envelope>" % self.bone.name
	
	def add_weight(self, vertex_index, weight_value):
		# (weight_value) is what percent the vertex at index (vertex_index) is influenced by (self.bone)
		self.vertices.append((vertex_index, weight_value))

class XSIParseError(Exception): pass

class Writer:
	def __init__(self, blend2xsi_xsi, f):
		self.xsi = blend2xsi_xsi
		self.file = f
		
		if f:
			self.write_xsi()
	
	def get_safe_name(self, name, sub="_"):
		ENABLE_NAME_WARNING = False
		
		if not name:
			name = "unnamed"
			if ENABLE_NAME_WARNING:
				print("XSI WRITER WARNING: Object with no name renamed to %r." % name)
		
		allowed = "QWERTYUIOPASDFGHJKLZXCVBNMqwertyuiopasdfghjklzxcvbnm1234567890_-"
		new_name = "".join((c if c in allowed else sub) for c in name)
		
		if ENABLE_NAME_WARNING and new_name != name:
			print("XSI WRITER WARNING: Object %r renamed to %r." % (new_name, name))
		
		return new_name
	
	def write(self, t=0, data=""):
		self.file.write("\t" * t + data + "\n")
	
	def write_vector_list(self, t, format_string, vectors):
		self.write(t, "%d;" % len(vectors))
		
		if not vectors: 
			return
		
		for vector in vectors[0:-1]:
			self.write(t, format_string % tuple(vector) + ",")
		else:
			self.write(t, format_string % tuple(vectors[-1],) + ";")
	
	def write_face_list(self, t, faces, indexed=True):
		def make_face(face):
			return "%d;" % len(face) + ",".join(str(i) for i in face) + ";"
		
		self.write(t, "%d;" % len(faces))
		
		if not faces: 
			return
		
		if not indexed:
			for face in faces[0:-1]:
				self.write(t, make_face(face) + ",")
			
			self.write(t, make_face(faces[-1]) + ";")
		else:
			for index, face in enumerate(faces[0:-1]):
				self.write(t, "%d;" % index + make_face(face) + ",")
			
			self.write(t, "%d;" % (len(faces)-1) + make_face(faces[-1]) + ";")
	
	def write_face_vertices(self, t, format_string, faces, vertices):
		self.write(t, "%d;" % len(vertices))
		if not vertices: return
		
		for face in faces:
			for index in face[0:-1]:
				self.write(t, format_string % tuple(vertices[index]) + ",")
			else:
				self.write(t, format_string % tuple(vertices[face[-1]]) + ";")
	
	def write_animationkeys(self, t, keys):
		self.write(t, "%d;" % len(keys))
		if not keys: return
		
		vector_size = len(keys[0][1])
		format_string = "%d; %d; " + ", ".join(["%f"] * vector_size) + ";;%s"
		
		for keyframe, vector in keys[0:-1]:
			self.write(t, format_string % (keyframe, vector_size, *vector, ","))
		self.write(t, format_string % (keys[-1][0], vector_size, *keys[-1][1], ";"))
	
	def write_xsi(self):
		self.write(0, "xsi 0101txt 0032\n") 
		
		self.write(0, "SI_CoordinateSystem coord {")
		self.write(1, "1;")
		self.write(1, "0;")
		self.write(1, "1;")
		self.write(1, "0;")
		self.write(1, "2;")
		self.write(1, "5;")
		self.write(0, "}\n")
		
		self.write(0, "SI_Angle {")
		self.write(1, "0;")
		self.write(0, "}\n")
		
		self.write(0, "SI_Ambience {")
		self.write(1, "0.000000; 0.000000; 0.000000;;")
		self.write(0, "}")
		
		for root_frame in self.xsi.frames:
			print("Writing object data...")
			
			self.write()			
			self.write_frame(0, root_frame)
		
		animated_frames = tuple(self.xsi.get_animated_frames())
		
		if animated_frames:
			print("Writing animation data...")
			
			self.write(0, "\nAnimationSet {")
			
			for frame in animated_frames:
				self.write_animation(1, frame)
			
			self.write(0, "}")
		
		skinned_frames = tuple(self.xsi.get_skinned_frames())
		
		if skinned_frames:
			print("Writing skin envelope data...")
			
			self.write(0, "\nSI_EnvelopeList {")
			self.write(1, "%d;" % self.xsi.get_envelope_count())
			
			for frame in skinned_frames:
				for envelope in frame.envelopes:
					self.write_envelope(1, frame, envelope)
			
			self.write(0, "}")
	
	def write_frame(self, t, frame):
		self.write(t, "Frame frm-%s {" % self.get_safe_name(frame.name))
		
		if frame.transform:
			self.write_matrix(t + 1, frame.transform, "FrameTransformMatrix")
		
		if frame.pose:
			self.write_matrix(t + 1, frame.pose, "SI_FrameBasePoseMatrix")
		
		if frame.mesh:
			self.write_mesh(t + 1, frame.mesh, frame.mesh.name if frame.mesh.name else frame.name)
		
		for sub_frame in frame.frames:
			self.write_frame(t + 1, sub_frame)
		
		self.write(t, "}")
	
	def write_matrix(self, t, matrix, block_name):
		self.write(t, block_name + " {")
		self.write(t + 1, "%f,%f,%f,%f,"  % tuple(matrix.right))
		self.write(t + 1, "%f,%f,%f,%f,"  % tuple(matrix.up))
		self.write(t + 1, "%f,%f,%f,%f,"  % tuple(matrix.front))
		self.write(t + 1, "%f,%f,%f,%f;;" % tuple(matrix.posit))
		self.write(t, "}")
	
	def write_mesh(self, t, mesh, name):
		self.write(t, "Mesh %s {" % self.get_safe_name(name))
		
		if mesh.vertices:
			self.write_vector_list(t + 1, "%f;%f;%f;", mesh.vertices)
			
			if mesh.faces:
				self.write_face_list(t + 1, mesh.faces, indexed = False)
			
			if mesh.face_materials and mesh.faces:
				face_material_indices, materials = mesh.get_material_indices()
				
				self.write(t + 1, "MeshMaterialList {")
				self.write(t + 2, "%d;" % len(materials))
				self.write(t + 2, "%d;" % len(face_material_indices))
				for index in face_material_indices[0:-1]:
					self.write(t + 2, "%d," % index)
				else:
					self.write(t + 2, "%d;" % face_material_indices[-1])
				
				for material in materials:
					self.write_material(t + 2, material)
				
				self.write(t + 1, "}")
			
			if mesh.normal_vertices:
				self.write(t + 1, "SI_MeshNormals {")
				self.write_vector_list(t + 2, "%f;%f;%f;", mesh.normal_vertices)
				
				if mesh.normal_faces:
					self.write_face_list(t + 2, mesh.normal_faces, indexed=True)
				
				self.write(t + 1, "}")
			
			if mesh.uv_vertices:
				self.write(t + 1, "SI_MeshTextureCoords {")
				self.write_vector_list(t + 2, "%f;%f;", mesh.uv_vertices)
				
				if mesh.uv_faces:
					self.write_face_list(t + 2, mesh.uv_faces, indexed=True)
				
				self.write(t + 1, "}")
			
			if mesh.vertex_colors and mesh.vertex_color_faces:
				self.write(t + 1, "SI_MeshVertexColors {")
				self.write_face_vertices(
					t + 2,
					"%f;%f;%f;%f;",
					mesh.vertex_color_faces,
					mesh.vertex_colors
				)
				self.write_face_list(t + 2, mesh.vertex_color_faces, indexed=True)
				self.write(t + 1, "}")
		
		self.write(t, "}")
	
	def write_material(self, t, material):
		self.write(t, "SI_Material {")
		self.write(t + 1, "%f;%f;%f;%f;;" % tuple(material.diffuse))
		self.write(t + 1, "%f;" % material.hardness)
		self.write(t + 1, "%f;%f;%f;;" % tuple(material.specular))
		self.write(t + 1, "%f;%f;%f;;" % tuple(material.emissive))
		self.write(t + 1, "%d;" % material.shading_type)
		self.write(t + 1, "%f;%f;%f;;" % tuple(material.ambient))
		
		if material.texture:
			self.write(t + 1, "SI_Texture2D {")
			self.write(t + 2, "\"%s\";" % material.texture)
			self.write(t + 1, "}")
		
		self.write(t, "}")
	
	def write_animation(self, t, frame):
		self.write(t, "Animation anim-%s {" % self.get_safe_name(frame.name))
		self.write(t + 1, "{frm-%s}" % self.get_safe_name(frame.name))
		
		for anim_key in frame.animation_keys:
			self.write(t + 1, "SI_AnimationKey {")
			self.write(t + 2, "%d;" % anim_key.key_type)
			self.write_animationkeys(t + 2, anim_key.keys)
			self.write(t + 1, "}")
		
		self.write(t, "}")
		
	def write_envelope(self, t, frame, envelope):
		self.write(t, "SI_Envelope {")
		self.write(t + 1, "\"frm-%s\";" % self.get_safe_name(frame.name))
		self.write(t + 1, "\"frm-%s\";" % self.get_safe_name(envelope.bone.name))
		self.write_vector_list(t + 1, "%d;%f;", envelope.vertices)
		self.write(t, "}")

def read(filepath, regex_skip_types=None):
	with open(filepath, "r") as f:
		if regex_skip_types == None:
			reader = Reader(f, bz2xsi_xsi=None, log_name=filepath) # Use defaults
		else:
			reader = Reader(f, bz2xsi_xsi=None, log_name=filepath, re_skip=regex_skip_types)
		
		return reader.xsi
