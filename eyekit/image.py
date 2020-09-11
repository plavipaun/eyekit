from os import path as _path
import re as _re
import numpy as _np
try:
	import cairosvg as _cairosvg
except ImportError:
	_cairosvg = None

_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

class Image:

	'''

	Visualization of texts and fixation sequences.

	'''

	def __init__(self, screen_width, screen_height):
		self.screen_width = screen_width
		self.screen_height = screen_height
		self.text_x = 0
		self.text_y = 0
		self.text_width = screen_width
		self.text_height = screen_height
		self.svg = ''
		self.label = None

	# PUBLIC METHODS

	def render_text(self, text_block, color='black'):
		svg = '<g id="text">\n\n'
		for r, line in enumerate(text_block.lines()):
			svg += '\t<g id="line_%i">\n' % r
			for char in line.chars:
				if char == ' ':
					continue
				svg += '\t\t<text text-anchor="middle" alignment-baseline="middle" x="%i" y="%i" fill="%s" style="font-size:%fpx; font-family:Courier New">%s</text>\n' % (char.x, char.y, color, text_block.fontsize, char)
			svg += '\t</g>\n\n'
		svg += '</g>\n\n'
		self.text_x = text_block.first_character_position[0] - (text_block.character_spacing * 0.5)
		self.text_y = text_block.first_character_position[1] - (text_block.line_spacing * 0.5)
		self.text_width = text_block.n_cols * text_block.character_spacing
		self.text_height = text_block.n_rows * text_block.line_spacing
		self.svg += svg

	def render_fixations(self, fixation_sequence, connect_fixations=True, color='black', discard_color='gray', number_fixations=False, include_discards=False):
		svg = '<g id="fixation_sequence">\n\n'
		last_fixation = None
		for i, fixation in enumerate(fixation_sequence.iter_with_discards()):
			if not include_discards and fixation.discarded:
				continue
			radius = _duration_to_radius(fixation.duration)
			if isinstance(color, list):
				this_color = color[i]
			else:
				this_color = color
			svg += '\t<g id="fixation_%i">\n' % i
			if connect_fixations and last_fixation:
				if include_discards and (last_fixation.discarded or fixation.discarded):
					svg += '\t\t<line x1="%i" y1="%i" x2="%i" y2="%i" style="stroke:%s;"/>\n' % (last_fixation.x, last_fixation.y, fixation.x, fixation.y, discard_color)
				else:
					svg += '\t\t<line x1="%i" y1="%i" x2="%i" y2="%i" style="stroke:%s;"/>\n' % (last_fixation.x, last_fixation.y, fixation.x, fixation.y, this_color)
			if include_discards and fixation.discarded:
				svg += '\t\t<circle cx="%i" cy="%i" r="%f" style="stroke-width:0; fill:%s; opacity:1.0" />\n' % (fixation.x, fixation.y, radius, discard_color)
			else:
				svg += '\t\t<circle cx="%i" cy="%i" r="%f" style="stroke-width:0; fill:%s; opacity:1.0" />\n' % (fixation.x, fixation.y, radius, this_color)
			last_fixation = fixation
			svg += '\t</g>\n\n'
		svg += '</g>\n\n'
		if number_fixations:
			svg += '<g id="fixation_numbers">\n'
			for i, fixation in enumerate(fixation_sequence.iter_with_discards()):
				if not include_discards and fixation.discarded:
					continue
				svg += '\t<text text-anchor="middle" alignment-baseline="middle" x="%i" y="%i" fill="white" style="font-size:10px; font-family:Helvetica">%s</text>\n' % (fixation.x, fixation.y, i+1)
			svg += '</g>\n\n'
		self.svg += svg

	def render_fixation_comparison(self, reference_sequence, fixation_sequence, color_match='black', color_mismatch='red'):
		svg = '<g id="fixation_comparison">\n\n'
		last_fixation = None
		for i, (reference_fixation, fixation) in enumerate(zip(reference_sequence.iter_with_discards(), fixation_sequence.iter_with_discards())):
			if reference_fixation.y == fixation.y:
				color = color_match
			else:
				color = color_mismatch
			radius = _duration_to_radius(fixation.duration)
			svg += '\t<g id="fixation_%i">\n' % i
			if last_fixation:
				svg += '\t\t<line x1="%i" y1="%i" x2="%i" y2="%i" style="stroke:black;"/>\n' % (last_fixation.x, last_fixation.y, fixation.x, fixation.y)
			svg += '\t\t<circle cx="%i" cy="%i" r="%f" style="stroke-width:0; fill:%s; opacity:1.0" />\n' % (fixation.x, fixation.y, radius, color)
			svg += '\t</g>\n\n'
			last_fixation = fixation
		svg += '</g>\n\n'
		self.svg += svg

	def render_heatmap(self, text_block, distribution, n=1, color='red'):
		svg = '<g id="heatmap">\n\n'
		distribution = _normalize_min_max(distribution)
		subcell_height = text_block.line_spacing / n
		levels = [subcell_height*i for i in range(n)]
		level = 0
		for ngram in text_block.iter_ngrams(n):
			if level == n:
				level = 0
			p = distribution[ngram[0].rc]
			subcell_width = ngram[-1].c - ngram[0].c + 1
			svg += '\t<rect x="%f" y="%f" width="%i" height="%i" style="fill:%s; stroke-width:0; opacity:%f" />\n\n' % (ngram[0].x-text_block.character_spacing/2., (ngram[0].y-text_block.line_spacing/2.)+levels[level], text_block.character_spacing*subcell_width, subcell_height, color, p)
			level += 1
		for line_i in range(text_block.n_rows-1):
			start_x = text_block.first_character_position[0] - (text_block.character_spacing - text_block.character_spacing/2)
			end_x = text_block.first_character_position[0] + (text_block.n_cols * text_block.character_spacing) - text_block.character_spacing/2
			y = text_block.first_character_position[1] + (text_block.line_spacing * line_i) + text_block.line_spacing/2
			svg += '\t<line x1="%f" y1="%f" x2="%f" y2="%f" style="stroke:black; stroke-width:2"/>\n\n' % (start_x, y, end_x, y)
		svg += '</g>\n\n'
		self.svg += svg

	def draw_line(self, start_xy, end_xy, color='black', dashed=False):
		start_x, start_y = start_xy
		end_x, end_y = end_xy
		if dashed:
			self.svg += '<line x1="%f" y1="%f" x2="%f" y2="%f" style="stroke:%s; stroke-width:2" stroke-dasharray="4" />\n\n' % (start_x, start_y, end_x, end_y, color)
		else:
			self.svg += '<line x1="%f" y1="%f" x2="%f" y2="%f" style="stroke:%s; stroke-width:2" />\n\n' % (start_x, start_y, end_x, end_y, color)

	def draw_circle(self, xy, radius=10, color='black'):
		x, y = xy
		self.svg += '<circle cx="%i" cy="%i" r="%f" style="stroke-width:0; fill:%s; opacity:1" />\n' % (x, y, radius, color)

	def draw_rectangle(self, x, y=None, width=None, height=None, color='black', dashed=False):
		if isinstance(x, tuple) and len(x) == 4:
			x, y, width, height = x
		if dashed:
			self.svg += '<rect x="%f" y="%f" width="%i" height="%i" style="fill:none; stroke:%s; stroke-width:2;" stroke-dasharray="4" />\n\n' % (x, y, width, height, color)
		else:
			self.svg += '<rect x="%f" y="%f" width="%i" height="%i" style="fill:none; stroke:%s; stroke-width:2;" />\n\n' % (x, y, width, height, color)

	def draw_text(self, x, y, text, color='black', align='left', css_style={}):
		css_style = '; '.join(['%s:%s'%(key, value) for key, value in css_style.items()])
		self.svg += '\t<text text-anchor="%s" alignment-baseline="middle" x="%i" y="%i" fill="%s" style="%s">%s</text>\n' % (align, x, y, color, css_style, text)

	def crop_to_text(self, margin=0):
		x_adjustment = self.text_x - margin
		y_adjustment = self.text_y - margin
		replacements = {}
		for x_param in ['cx', 'x1', 'x2', 'x']:
			search_string = '( %s="(.+?)")' % x_param
			for match in _re.finditer(search_string, self.svg):
				surround, value = match.groups()
				new_value = int(float(value) - x_adjustment)
				replacement = surround.replace(value, str(new_value))
				replacements[surround] = replacement
		regex = _re.compile("(%s)" % '|'.join(map(_re.escape, replacements.keys())))
		svg = regex.sub(lambda mo: replacements[mo.string[mo.start():mo.end()]], self.svg)
		replacements = {}
		for y_param in ['cy', 'y1', 'y2', 'y']:
			search_string = '( %s="(.+?)")' % y_param
			for match in _re.finditer(search_string, svg):
				surround, value = match.groups()
				new_value = int(float(value) - y_adjustment)
				replacement = surround.replace(value, str(new_value))
				replacements[surround] = replacement
		regex = _re.compile("(%s)" % '|'.join(map(_re.escape, replacements.keys())))
		svg = regex.sub(lambda mo: replacements[mo.string[mo.start():mo.end()]], svg)
		self.screen_width = self.text_width + 2 * margin
		self.screen_height = self.text_height + 2 * margin
		self.svg = svg

	def set_label(self, label):
		self.label = label

	def save(self, output_path, image_width=200):
		if _cairosvg is None and not output_path.endswith('.svg'):
			raise ValueError('Cannot save to this format. Use .svg or install cairosvg to save as .pdf, .eps, or .png.')
		image_height = self.screen_height / (self.screen_width / image_width)
		image_size = '' if output_path.endswith('.png') else 'width="%fmm" height="%fmm"' % (image_width, image_height)
		svg = '<svg %s viewBox="0 0 %i %i" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:svg="http://www.w3.org/2000/svg" xmlns="http://www.w3.org/2000/svg" version="1.1">\n\n<rect width="%i" height="%i" fill="white"/>\n\n' % (image_size, self.screen_width, self.screen_height, self.screen_width, self.screen_height)
		svg += self.svg
		svg += '</svg>'
		with open(output_path, mode='w', encoding='utf-8') as file:
			file.write(svg)
		if not output_path.endswith('.svg'):
			convert_svg(output_path, output_path)


def convert_svg(svg_file_path, out_file_path):
	'''

	Convert an SVG file into PDF, EPS, or PNG. This function is
	essentially a wrapper around CairoSVG.
	
	'''
	if _cairosvg is None:
		raise ValueError('CairoSVG is required to convert SVGs to another format.')
	filename, extension = _path.splitext(out_file_path)
	if extension == '.pdf':
		_cairosvg.svg2pdf(url=svg_file_path, write_to=out_file_path)
	elif extension == '.eps':
		_cairosvg.svg2ps(url=svg_file_path, write_to=out_file_path)
	elif extension == '.png':
		_cairosvg.svg2png(url=svg_file_path, write_to=out_file_path)
	else:
		raise ValueError('Cannot save to this format. Use either .pdf, .eps, or .png')

def combine_images(images, output_path, image_width=200, image_height=None, v_padding=5, h_padding=5, e_padding=1, auto_letter=True):
	'''

	Combine image objects together into one larger image. `images` should
	be a *list* of *list* of `Image` structure. For example, `[[img1, img2], [img3, img4]]`
	results in a 2x2 grid of images. `image_width` is the desired mm
	(SVG, PDF, EPS) or pixel (PNG) width of the combined image. If
	`auto_letter` is set to `True`, each image will be given a letter
	label.

	'''
	svg = ''
	l = 0
	y = e_padding
	for row in images:
		x = e_padding
		tallest_in_row = 0
		if auto_letter or sum([bool(image.label) for image in row if isinstance(image, Image)]):
			y += 2.823 + 1 # row contains labels, so make some space
		n_cols = len(row)
		cell_width = (image_width - 2 * e_padding - (n_cols-1) * h_padding) / n_cols
		for image in row:
			if image is None:
				x += cell_width + h_padding
				continue
			scaling_factor = cell_width / image.screen_width
			aspect_ratio = image.screen_width / image.screen_height
			cell_height = cell_width / aspect_ratio
			if cell_height > tallest_in_row:
				tallest_in_row = cell_height
			label = None
			if auto_letter and image.label:
				label = '<tspan style="font-weight:bold">(%s)</tspan> %s' % (_ALPHABET[l], image.label)
			elif auto_letter:
				label = '<tspan style="font-weight:bold">(%s)</tspan>' % _ALPHABET[l]
			elif image.label:
				label = image.label
			if label:
				svg += '<text x="%f" y="%f" fill="black" style="font-size:2.823; font-family:Helvetica">%s</text>\n\n' % (x, y-2, label)
			svg += '<g transform="translate(%f, %f) scale(%f)">' % (x, y, scaling_factor)
			svg += image.svg
			svg += '</g>'
			svg += '<rect x="%f" y="%f" width="%f" height="%f" fill="none" stroke="black" style="stroke-width:0.25" />\n\n' % (x, y, cell_width, cell_height)			
			x += cell_width + h_padding
			l += 1
		y += tallest_in_row + v_padding
	if image_height is None:
		image_height = y - (v_padding - e_padding)
	if _cairosvg is None and not output_path.endswith('.svg'):
		raise ValueError('Cannot save to this format. Use .svg or install cairosvg to save as .pdf, .eps, or .png.')
	image_size = '' if output_path.endswith('.png') else 'width="%fmm" height="%fmm"' % (image_width, image_height)
	svg = '<svg %s viewBox="0 0 %i %i" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:svg="http://www.w3.org/2000/svg" xmlns="http://www.w3.org/2000/svg" version="1.1">\n\n<rect width="%i" height="%i" fill="white"/>\n\n%s\n\n</svg>' % (image_size, image_width, image_height, image_width, image_height, svg)
	with open(output_path, mode='w', encoding='utf-8') as file:
		file.write(svg)
	if not output_path.endswith('.svg'):
		convert_svg(output_path, output_path)


def _normalize_min_max(distribution):
	'''

	Normalizes a numpy array such that the minimum value becomes 0 and
	the maximum value becomes 1.
	
	'''
	return (distribution - distribution.min()) / (distribution.max() - distribution.min())

def _duration_to_radius(duration):
	'''

	Converts a millisecond duration to a pixel radius for plotting
	fixation circles so that the area of the circle corresponds to
	duration.
	
	'''
	return _np.sqrt(duration / _np.pi)
