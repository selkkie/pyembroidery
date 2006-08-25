# PyEmbroidery
#
# wxPython program for viewing (and eventually editing and digitizing)
# embroidery designs for use on home sewing machines.
#
# Created by Jackson Yee (jackson.yee@gmail.com)
# Project located at http://pyembroidery.googlecode.com/
#
# All code here is released under the GPL version 2 at
# http://www.gnu.org/copyleft/gpl.html
#
# Enjoy what's here so far, and send any bug fixes back to me!

#!/usr/bin/python

import sys
import os
import wx
import re
import random
import StringIO
import array
import math

APP_NAME	=	'PyEmbroidery (by Jackson Yee)' 

# IDs
(	NEW_TAB,
	CLOSE_TAB,
	ROTATE_CLOCKWISE,
	ROTATE_COUNTERCLOCKWISE,
	OPEN_IMAGE,
	CLOSE_IMAGE,
	MOVE_LEFT,
	MOVE_RIGHT,
	MOVE_UP,
	MOVE_DOWN,
)	=	range( wx.ID_HIGHEST, wx.ID_HIGHEST + 10)

# *********************************************************************
class Sketch(object):
	
	# -------------------------------------------------------------------
	def __init__(self):
		self.Clear()
	
	# -------------------------------------------------------------------
	def Clear(self):
		if hasattr(self, 'Image'):
			if self.Image:
				self.Image.Destroy()
			
		self.Image	=	None
		self.Design	=	Design()
		self.UndoList	=	[]
	
	# -------------------------------------------------------------------
	def LoadImage(self, filename):
		self.Image.LoadFile(filename, wx.BITMAP_TYPE_ANY)

# *********************************************************************
class Design(object):
	JUMP	=	0x01
	COLOR	=	0x02
	
	# -------------------------------------------------------------------
	def __init__(self):
		self.Clear()
	
	# -------------------------------------------------------------------
	def Clear(self):
		self.Name						=	'Untitled'
		self.ColorsRead				=	0
		self.Colors						=	[]
		self.Stitches					=	[]
		self.CurrentStitch		=	0
		self.StitchCount			=	0
		self.JumpStitches			=	[]
		self.ColorChanges			=	[]
		self.Begin						=	(0, 0)
		self.Width						=	0
		self.Height						=	0
		self.LastX						=	0
		self.LastY						=	0
		self.MaxX							=	0
		self.MaxY							=	0
		self.MinX							=	0
		self.MinY							=	0
	
	# -------------------------------------------------------------------
	def RandomColor(self):
		return (	random.randint(0x00, 0xc0),
							random.randint(0x00, 0xc0),  
							random.randint(0x00, 0xc0), 
						)
	
	# -------------------------------------------------------------------
	def Valid(self):
		return len(self.Stitches)
		
	# -------------------------------------------------------------------
	def CalcStitchExtent(self):
		maxx = 0
		maxy = 0
		minx = 0
		miny = 0
		
		for s in self.Stitches:
			if len(s) == 3:
				if s[2] == self.COLOR:
					continue
				
			if s[0] > maxx:
				maxx = s[0]
			elif s[0] < minx:
				minx = s[0]
				
			if s[1] > maxy:
				maxy = s[1]
			elif s[1] < miny:
				miny = s[1]
		
		self.MaxX = maxx
		self.MaxY = maxy
		self.MinX = minx
		self.MinY = miny
		self.Width	=	maxx - minx
		self.Height	=	maxy - miny
		
		NumColors = 1
		
		for s in self.Stitches:
			if len(s) == 3:
				if s[2] == self.COLOR:
					NumColors += 1
		
		print '%s colors in design, found %s colors in file' % ( len( self.Colors ), NumColors )
		print '%s stitches, %s jump stitches, %s color changes' % ( len(self.Stitches) - len(self.JumpStitches) - len(self.ColorChanges), len(self.JumpStitches), len(self.ColorChanges) )
		print 'Design has extents of width %.1f mm from (%.1f mm, %.1f mm) and height %.1f mm from (%.1f mm, %.1f mm)' % (self.Width / 10.0, self.MinX / 10.0, self.MaxX / 10.0, self.Height / 10.0, self.MinY / 10.0, self.MaxY / 10.0)
		
	# -------------------------------------------------------------------
	def Load(self, filename):
		self.Clear()
		if len(filename) > 4:
			if filename[-4:] == '.dst':
				self.LoadTajima(filename)
				self.CalcStitchExtent()
				return
		
		raise ValueError("""I can't figure out what type of embroidery design is in this file. Please make sure that the file has the proper extension.""")
	
	# -------------------------------------------------------------------
	def Save(self, filename):
		self.LastX	=	0
		self.LastY	=	0
		
		if len(filename) > 4:
			if filename[-4:] == '.dst':
				return self.SaveTajima(filename)
		
		raise ValueError("""I can't figure out what type of embroidery design is in this file. Please make sure that the file has the proper extension.""")
	
	# -------------------------------------------------------------------
	def LoadTajima(self, filename):
		self.Colors = []
		
		try:
			f = file(filename + '.colors', 'r')		
			
			for l in f:
				if len(l) >= 7:
					r = int(l[1:3], 16)
					g = int(l[3:5], 16)
					b = int(l[5:7], 16)
					self.Colors.append( (r, g, b) )
			
			f.close()
		except Exception, e:
			print 'Could not read colors file: %s' % e
		
		f = file(filename, 'rb')
		
		header = f.read(512)
		
		lines = header.split('\n')
		
		values = {}
		
		for l in lines:
			length = len(l)
			
			if length > 3:
				if l[2] == ':':
					values[ l[0:2] ] = l[3:]
		
		f.seek(512)
		
		stitches = []
		
		if not len(self.Colors):
			self.Colors.append( self.RandomColor() )
			self.ColorsRead += 1
		
		while True:
			rec = f.read(3)
			
			# Bad record or end of file
			if len(rec) < 3:
				break
			
			b1 = ord(rec[0])
			b2 = ord(rec[1])
			b3 = ord(rec[2])
			
			# End of file
			if b3 == 0xF3:
				break
			
			self.Stitches.append( self.DecodeTajimaStitch(b1, b2, b3) )
			self.CurrentStitch += 1
		
		f.close()
		
		for s in self.Stitches:
			if len(s) == 3:
				if s[2] == self.COLOR:
					continue
			
			s[1] = -s[1]
		
	# -------------------------------------------------------------------
	def DecodeTajimaStitch(self, b1, b2, b3):		
		x = self.LastX
		y = self.LastY
		
		if b1 & 0x01:
			x += 1
			
		if b1 & 0x02:
			x -= 1
			
		if b1 & 0x04:
			x += 9
			
		if b1 & 0x08:
			x -= 9
			
		if b1 & 0x80:
			y += 1
			
		if b1 & 0x40:
			y -= 1
			
		if b1 & 0x20:
			y += 9
			
		if b1 & 0x10:
			y -= 9
			
		if b2 & 0x01:
			x += 3
			
		if b2 & 0x02:
			x -= 3
			
		if b2 & 0x04:
			x += 27
			
		if b2 & 0x08:
			x -= 27
			
		if b2 & 0x80:
			y += 3
		
		if b2 & 0x40:
			y -= 3
			
		if b2 & 0x20:
			y += 27
			
		if b2 & 0x10:
			y -= 27
			
		if b3 & 0x04:
			x += 81
			
		if b3 & 0x08:
			x -= 81
			
		if b3 & 0x20:
			y += 81
			
		if b3 & 0x10:
			y -= 81
		
		# Color change
		if b3 & 0x80 and b3 & 0x40:
			self.ColorsRead += 1
			if self.ColorsRead > len(self.Colors):
				self.Colors.append( self.RandomColor() )
			
			self.ColorChanges.append( self.CurrentStitch ) 
			return [self.ColorsRead - 1, 0, self.COLOR]
		
		self.LastX = x
		self.LastY = y
		
		# Jump stitch
		if b3 & 0x80:
			self.JumpStitchCount += 1
			self.JumpStitches.append( self.CurrentStitch ) 
			return [x, y, self.JUMP]
			
		self.StitchCount += 1
		return [x, y]
		
	# -------------------------------------------------------------------
	def EncodeTajimaStitch(self, s):
		b1 = 0
		b2 = 0
		b3 = 0
		
		rec = array.array('c', '\0\0\0')
		
		if len(s) == 3:
			if s[2] == self.COLOR:
				rec[0] = chr(0)
				rec[1] = chr(0)
				rec[2] = chr(0xc3)
				return rec.tostring()
			elif s[2] == self.JUMP:
				s3 = self.JUMP
		else:
			s3 = 0
		
		dx = s[0] - self.LastX
		dy = s[1] - self.LastY		
		
		self.LastX = s[0]
		self.LastY = s[1]
		
		if dx > 40:
			b3 |= 0x04
			dx -= 81
		
		if dx < -40:
			b3 |= 0x08
			dx += 81
			
		if dy > 40:
			b3 |= 0x20
			dy -= 81
		
		if dy < -40:
			b3 |= 0x10
			dy += 81

		if dx > 13:
			b2 |= 0x04
			dx -= 27
		
		if dx < -13:
			b2 |= 0x08
			dx += 27
			
		if dy > 13:
			b2 |= 0x20
			dy -= 27
		
		if dy < -13:
			b2 |= 0x10
			dy += 27
		
		if dx > 4:
			b1 |= 0x04
			dx -= 9
		
		if dx < -4:
			b1 |= 0x08
			dx += 9
			
		if dy > 4:
			b1 |= 0x20
			dy -= 9
		
		if dy < -4:
			b1 |= 0x10
			dy += 9
			
		if dx > 1:
			b2 |= 0x01
			dx -= 3
		
		if dx < -1:
			b2 |= 0x02
			dx += 3
			
		if dy > 1:
			b2 |= 0x80
			dy -= 3
		
		if dy < -1:
			b2 |= 0x40
			dy += 3
		
		if dx > 0:
			b1 |= 0x01
			dx -= 1
		
		if dx < 0:
			b1 |= 0x02
			dx += 1
			
		if dy > 0:
			b1 |= 0x80 
			dy -= 1
		
		if dy < 0:
			b1 |= 0x40
			dy += 1
		
		if s3 == self.JUMP:
			rec[0] = chr(b1)
			rec[1] = chr(b2)
			rec[2] = chr(b3 | 0x83)
			return rec.tostring()
		
		rec[0] = chr(b1)
		rec[1] = chr(b2)
		rec[2] = chr(b3 | 0x03)
		return rec.tostring()
		
	# -------------------------------------------------------------------
	def SaveTajima(self, filename):
		f = file(filename, 'wb')
		
		for i in range(0, 512):
			f.write(' ')
		
		f.seek(512)
		
		for s in self.Stitches:
			f.write( self.EncodeTajimaStitch( s ) )
		
		rec = array.array('c')
		rec.append( chr(0) )
		rec.append( chr(0) )
		rec.append( chr(0xF3) )
		
		f.write(rec.tostring())
		f.close()
		
		f = file(filename + '.colors', 'w')
		
		for c in self.Colors:
			f.write( '#%02X%02X%02X\n' % ( c[0], c[1], c[2] ) )
		
		f.close()
		
	# -------------------------------------------------------------------
	def Move(self, dx, dy):
		for s in self.Stitches:
			if len(s) == 3:
				if s[2] == self.COLOR:
					continue
			
			s[0] += dx
			s[1] += dy			
	
	# -------------------------------------------------------------------
	def Rotate(self, angle):
		# Calculate center of image
		cx = self.MinX + (self.Width / 2)
		cy = self.MinY + (self.Height / 2)
		
		angle = math.radians(angle)
		
		for s in self.Stitches:
			if len(s) == 3:
				if s[2] == self.COLOR:
					continue
			
			sa = math.sin(angle)
			ca = math.cos(angle)
			
			# Transform using center
			dx = s[0] - cx
			dy = s[1] - cy
			
			# Calculate new coordinates
			nx = (dx * ca - dy * sa)
			ny = (dy * ca + dx * sa)
			
			# Transform back
			s[0] = nx + cx
			s[1] = ny + cy

# *********************************************************************
class ToolCtrl(wx.Window):
	
	# -------------------------------------------------------------------
	def __init__(self, parent, wid, pstyle):
		wx.Window.__init__(self, parent, wid, style = pstyle)

# *********************************************************************
class SketchCtrl(wx.Window):
	
	# -------------------------------------------------------------------
	def __init__(self, parent, wid, pstyle):
		wx.Window.__init__(self, parent, wid, style = pstyle)
		
		self.Clear()
		
		self.Bind( wx.EVT_PAINT, self.OnPaint )
		self.Bind( wx.EVT_KEY_DOWN, self.OnKeyDown )		
		
	# -------------------------------------------------------------------
	def Clear(self):
		self.CurrentFile		=	None
		self.cx							=	0
		self.cy							=	0
		self.Magnification	=	1.0
		self.Modified				=	False
		
		self.Sketch 				= Sketch()
		
		self.Refresh()
		
	# -------------------------------------------------------------------
	def OnPaint(self, e):
		dc = wx.PaintDC(self)
		
		w, h = dc.GetSizeTuple()
		
		dc.SetBrush( wx.WHITE_BRUSH )
		dc.DrawRectangle( 0, 0, w, h )
		dc.SetBrush( wx.NullBrush )
		
		m = self.Magnification
		dc.SetUserScale(m, m)
		
		self.DrawImage(dc, self.cx, self.cy)
		self.DrawDesign(dc, self.cx, self.cy)
	
	# -------------------------------------------------------------------
	def DrawImage(self, dc, cx, cy):
		if not self.Sketch.Image:
			return
		
		dc.DrawBitmap( wx.BitmapFromImage( self.Sketch.Image ), 
			cx - (self.Sketch.Image.GetWidth() / 2), 
			cy - (self.Sketch.Image.GetHeight() / 2))
		
	# -------------------------------------------------------------------
	def DrawDesign(self, dc, cx, cy):
		if not self.Sketch.Design.Valid():
			return
			
		c = wx.Colour( self.Sketch.Design.Colors[0][0], 
									self.Sketch.Design.Colors[0][1],
									self.Sketch.Design.Colors[0][2],
			)
		
		p = wx.Pen( c )
		dc.SetPen( p )
		
		x = 0
		y = 0
		
		for s in self.Sketch.Design.Stitches:
			if len(s) == 3:
				if s[2] == Design.COLOR:
					i = s[0]
					c = wx.Colour( self.Sketch.Design.Colors[i][0], 
												self.Sketch.Design.Colors[i][1],
												self.Sketch.Design.Colors[i][2],
					)
					
					p = wx.Pen(c)
					dc.SetPen( wx.NullPen )
					dc.SetPen( p )
					continue
					
			dc.DrawLine(x + cx, y + cy, s[0] + cx, s[1] + cy)
			print 'Drawing from (%d, %d) to (%d, %d)' % (x + cx, y + cy, s[0] + cx, s[1] + cy) 
			x = s[0]
			y = s[1]
		
		dc.SetPen( wx.NullPen )		
		print 'cx, cy = (%d, %d)' % (self.cx, self.cy)
	
	# -------------------------------------------------------------------
	def OnRotateClockwise(self, e):
		if self.Sketch.Design.Valid():
			self.Sketch.Design.Rotate(90)
			self.Modified = True
			self.Refresh()
	
	# -------------------------------------------------------------------
	def OnRotateCounterClockwise(self, e):
		if self.Sketch.Design.Valid():
			self.Sketch.Design.Rotate(270)
			self.Modified = True
			self.Refresh()
			
	# -------------------------------------------------------------------
	def OnOpen(self, e):
		dlg = wx.FileDialog(self, 
						'Which embroidery design would you like to open?',
						wildcard = 'Design files (*.dst)|*.dst|All files (*.*)|*.*',
						style = wx.OPEN | wx.FILE_MUST_EXIST)
		
		if dlg.ShowModal() == wx.ID_OK:
			try:
				p = dlg.GetPath()
				d = self.Sketch.Design
				d.Load( p )
				self.cx = -d.MinX + 12
				self.cy = -d.MinY + 12
				self.CurrentFile = p
				self.Modified = False
			except Exception, e:
				wx.MessageBox('Could not read the file that you wanted to load: %s' % e,
					"Hmm... there's a problem here",
					wx.ICON_ERROR | wx.OK)
	
	# -------------------------------------------------------------------
	def OnOpenImage(self, e):
		dlg = wx.FileDialog(self, 
						'Which image would you like to open?',
						wildcard = 'All images (*.bmp;*.png;*.jpg;*.gif;*.pcx;*.tif;*.xpm)|*.bmp;*.png;*.jpg;*.gif;*.pcx;*.tif;*.xpm|All files (*.*)|*.*',
						style = wx.OPEN | wx.FILE_MUST_EXIST)
		
		if dlg.ShowModal() == wx.ID_OK:
			try:
				p = dlg.GetPath()
				self.Sketch.Image = wx.Image(p)				
				self.Modified = False
				self.Refresh()
			except Exception, e:
				wx.MessageBox('Could not read the file that you wanted to load: %s' % e,
					"Hmm... there's a problem here",
					wx.ICON_ERROR | wx.OK)
	
	# -------------------------------------------------------------------
	def OnCloseImage(self, e):
		self.Sketch.Image = None
		self.Refresh()
	
	# -------------------------------------------------------------------
	def OnSave(self, e):
		if not self.Modified:
			return
			
		if not self.CurrentFile:
			return self.OnSaveAs(e)
		
		try:
			self.Sketch.Design.Save( self.CurrentFile )
			self.Modified = False
		except Exception, e:
			wx.MessageBox('Could not save the current design: %s' % e,
				"Hmm... there's a problem here",
				wx.ICON_ERROR | wx.OK)
	
	# -------------------------------------------------------------------
	def OnSaveAs(self, e):
		dlg = wx.FileDialog(self, 
						'Which embroidery design would you like to open?',
						wildcard = 'Design files (*.dst)|*.dst|All files (*.*)|*.*',
						style = wx.SAVE)
		
		if dlg.ShowModal() == wx.ID_OK:
			try:
				p = dlg.GetPath()
				self.Sketch.Design.Save( p )
				self.CurrentFile = p
				self.Modified = False
			except Exception, e:
				wx.MessageBox('Could not save the current design: %s' % e,
					"Hmm... there's a problem here",
					wx.ICON_ERROR | wx.OK)	
					
	# -------------------------------------------------------------------
	def OnKeyDown(self, e):
		c = e.GetKeyCode()
		
		if c == wx.WXK_LEFT:
			self.ProcessCommand( MOVE_LEFT ) 
		elif c == wx.WXK_RIGHT:
			self.ProcessCommand( MOVE_RIGHT ) 
		elif c == wx.WXK_UP:
			self.ProcessCommand( MOVE_UP ) 
		elif c == wx.WXK_DOWN:
			self.ProcessCommand( MOVE_DOWN ) 
		elif c == wx.WXK_NUMPAD_ADD:
			self.ProcessCommand( wx.ID_ZOOM_IN ) 
		elif c == wx.WXK_NUMPAD_SUBTRACT:		
			self.ProcessCommand( wx.ID_ZOOM_OUT ) 
	
	# -------------------------------------------------------------------
	def ProcessCommand(self, c):
		self.Freeze()
		
		if c == MOVE_LEFT:
			self.cx -= 4
		elif c == MOVE_RIGHT:
			self.cx += 4
		elif c == MOVE_UP:
			self.cy -= 4
		elif c == MOVE_DOWN:
			self.cy += 4
		elif c == wx.ID_ZOOM_IN:
			self.OnZoomIn( c )
		elif c == wx.ID_ZOOM_OUT:
			self.OnZoomOut( c )
		elif c == OPEN_IMAGE:
			self.OnOpenImage( c )
		elif c == CLOSE_IMAGE:
			self.OnCloseImage( c )
			
		self.Refresh()
		
		self.Thaw()
	
	# -------------------------------------------------------------------
	def OnZoomIn(self, e):
		self.Magnification += 0.1		
		self.Refresh()
	
	# -------------------------------------------------------------------
	def OnZoomOut(self, e):
		self.Magnification -= 0.1		
		self.Refresh()

# *********************************************************************
class ColorsCtrl(wx.ScrolledWindow):
	
	# -------------------------------------------------------------------
	def __init__(self, parent, wid, sketchctrl, pstyle):
		wx.ScrolledWindow.__init__(self, parent, wid, style = pstyle)
		
		self.SketchCtrl = sketchctrl

		dc = wx.WindowDC(self)
		tw, th = dc.GetTextExtent( 'Jj' )
		
		self.TextWidth = th
		self.TextHeight = th
		
		self.Bind( wx.EVT_PAINT, self.OnPaint )
		self.Bind( wx.EVT_LEFT_DOWN, self.OnLeftDown )
		
		self.SetScrollRate(10, 10)
		
	# -------------------------------------------------------------------
	def OnLeftDown(self, e):
		i = e.GetY() / self.TextHeight
		Colors = self.SketchCtrl.Sketch.Design.Colors
		
		if i < len( Colors ):
			dlg = wx.ColourDialog(self)
			
			if dlg.ShowModal() == wx.ID_OK:
				c = dlg.GetColourData().GetColour()
				Colors[i] = (c.Red(), c.Green(), c.Blue())
				self.SketchCtrl.Modified = True
				self.SketchCtrl.Refresh()
				self.GetParent().GetParent().GetParent().UpdateTitle()
				
	# -------------------------------------------------------------------
	def OnPaint(self, e):
		dc = wx.PaintDC(self)
		
		w, h = dc.GetSizeTuple()
		
		dc.SetBrush( wx.WHITE_BRUSH )
		dc.DrawRectangle( 0, 0, w, h )
		dc.SetBrush( wx.NullBrush )
		
		x, y = 0, 0
		
		for c in self.SketchCtrl.Sketch.Design.Colors:
			color = wx.Colour( c[0], c[1], c[2] )			
			brush = wx.Brush( color )
			dc.SetBrush( brush )
			
			dc.DrawRectangle( x, y, w, self.TextHeight )
			
			text = '#%02X%02X%02X' % ( c[0], c[1], c[2] )
			
			ca = (c[0] + c[1] + c[2]) / 3
			
			if ca > 0xa0:
				dc.SetTextForeground( wx.Colour( 0x00, 0x00, 0x00 ) )
			else:
				dc.SetTextForeground( wx.Colour( 0xff, 0xff, 0xff ) )
			
			tw, th = dc.GetTextExtent( text )
			dc.DrawText( text, (w / 2) - (tw / 2), y )
			
			y += self.TextHeight
			
			dc.SetBrush( wx.NullBrush )
		
	# -------------------------------------------------------------------
	def Update(self):
		self.SetVirtualSizeHints(self.TextWidth * 4, 
			len( self.SketchCtrl.Sketch.Design.Colors ) * self.TextHeight)
		
		self.Refresh()
		
# *********************************************************************
class MainWnd(wx.Frame):	
	# -------------------------------------------------------------------
	def __init__(self, parent, wid, title):
		wx.Frame.__init__(self,
										parent,
										wx.ID_ANY,
										title)
		
		self.Splitter = wx.SplitterWindow(self, wx.ID_ANY, style = wx.SP_3D)
		
		self.Tabs	=	wx.Notebook(self.Splitter, wx.ID_ANY, style = wx.NB_TOP)		
		self.SideBar	=	wx.Notebook(self.Splitter, wx.ID_ANY, style = wx.NB_TOP)		
		
		self.CreateToolBar()
		
		self.Splitter.SplitVertically( self.SideBar, self.Tabs )
		
		self.MainSizer = wx.BoxSizer( wx.HORIZONTAL )
		self.MainSizer.Add( self.Splitter, 1, wx.EXPAND )
		self.SetSizer( self.MainSizer )
		
		self.Tabs.AddPage( SketchCtrl(self.Tabs, wx.ID_ANY, 0), 'Untitled' )
		self.Tabs.GetCurrentPage().SetFocus()
		
		self.SideBar.AddPage( ColorsCtrl(self.SideBar, wx.ID_ANY, self.Tabs.GetCurrentPage(), 0), 'Color Editor' )
		
		self.MainMenu	=	wx.MenuBar()
		
		self.FileMenu	=	wx.Menu()
		
		self.FileMenu.Append(	wx.ID_NEW, 'New Design\tCtrl+N' )
		self.FileMenu.Append(	NEW_TAB, 'New Tab\tCtrl+T' )
		self.FileMenu.AppendSeparator()
		self.FileMenu.Append(	wx.ID_OPEN, 'Open Design\tCtrl+O' )
		self.FileMenu.Append(	OPEN_IMAGE, 'Open Image\tShift+Ctrl+O' )
		self.FileMenu.Append(	wx.ID_SAVE, 'Save Design\tCtrl+S' )
		self.FileMenu.Append(	wx.ID_SAVEAS, 'Save Design As\tShift+Ctrl+S' )
		self.FileMenu.AppendSeparator()
		self.FileMenu.Append(	CLOSE_TAB, 'Close Tab\tCtrl+W' )
		self.FileMenu.Append(	CLOSE_IMAGE, 'Close Image\tShift+Ctrl+W' )
		self.FileMenu.Append(	wx.ID_EXIT, 'Exit This Program\tAlt+F4' )
		
		self.ViewMenu	=	wx.Menu()
		
		self.ViewMenu.Append(	wx.ID_ZOOM_IN, 'Zoom In\t+' )
		self.ViewMenu.Append(	wx.ID_ZOOM_OUT, 'Zoom Out\t-' )
		self.ViewMenu.AppendSeparator()
		self.ViewMenu.Append(	ROTATE_CLOCKWISE, 'Rotate Clockwise\tR' )
		self.ViewMenu.Append(	ROTATE_COUNTERCLOCKWISE, 'Rotate Counterclockwise\tL' )
		
		self.HelpMenu	=	wx.Menu()
		
		self.HelpMenu.Append( wx.ID_HELP_CONTENTS, 'Read the Manual' )
		self.HelpMenu.AppendSeparator()
		self.HelpMenu.Append( wx.ID_ABOUT, 'About This Program' )
		
		self.MainMenu.Append( self.FileMenu, 'File' )
		self.MainMenu.Append( self.ViewMenu, 'View' )
		self.MainMenu.Append( self.HelpMenu, 'Help' )
		
		self.SetMenuBar( self.MainMenu )
		
		self.Bind( wx.EVT_MENU, self.OnNew, id = wx.ID_NEW )
		self.Bind( wx.EVT_MENU, self.OnNewTab, id = NEW_TAB )
		self.Bind( wx.EVT_MENU, self.OnCloseTab, id = CLOSE_TAB )
		self.Bind( wx.EVT_MENU, self.OnOpen, id = wx.ID_OPEN )
		self.Bind( wx.EVT_MENU, self.OnSave, id = wx.ID_SAVE )
		self.Bind( wx.EVT_MENU, self.OnSaveAs, id = wx.ID_SAVEAS )
		self.Bind( wx.EVT_MENU, self.ProcessCommand, id = wx.ID_ZOOM_IN )
		self.Bind( wx.EVT_MENU, self.ProcessCommand, id = wx.ID_ZOOM_OUT )
		self.Bind( wx.EVT_MENU, self.OnRotateClockwise, id = ROTATE_CLOCKWISE )
		self.Bind( wx.EVT_MENU, self.OnRotateCounterClockwise, id = ROTATE_COUNTERCLOCKWISE )
		self.Bind( wx.EVT_MENU, self.ProcessCommand, id = OPEN_IMAGE )
		self.Bind( wx.EVT_MENU, self.ProcessCommand, id = CLOSE_IMAGE )
		
		self.Bind( wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnTabChange)
		
		self.Accelerators = wx.AcceleratorTable(
			[
				(wx.ACCEL_CTRL,	ord('O'),	wx.ID_OPEN),
				(wx.ACCEL_CTRL,	ord('N'),	NEW_TAB),
				(wx.ACCEL_CTRL,	ord('W'),	CLOSE_TAB),
				(wx.ACCEL_CTRL,	ord('S'),	wx.ID_SAVE),
				(wx.ACCEL_CTRL,	ord('R'),	ROTATE_CLOCKWISE),
				(wx.ACCEL_CTRL,	ord('S'),	ROTATE_COUNTERCLOCKWISE),
				(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('S'),	wx.ID_SAVEAS),
				(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('O'),	OPEN_IMAGE),
				(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('W'),	CLOSE_IMAGE),
			]
		)
			
		self.SetAcceleratorTable( self.Accelerators )		
		
	# -------------------------------------------------------------------
	def OnNew(self, e):
		self.Tabs.GetCurrentPage().Clear()
		self.UpdateTitle()
		self.UpdateSideBar()
	
	# -------------------------------------------------------------------
	def OnNewTab(self, e):
		self.Tabs.AddPage( SketchCtrl(self.Tabs, wx.ID_ANY, 0), 'Untitled', True)
		self.UpdateSideBar()
		
	# -------------------------------------------------------------------
	def OnCloseTab(self, e):
		if self.Tabs.GetPageCount() > 1:
			self.Tabs.DeletePage( self.Tabs.GetSelection() )
		else:
			self.Tabs.GetCurrentPage().Clear()
			self.Tabs.GetCurrentPage().Refresh()
			
		self.UpdateSideBar()
		
	# -------------------------------------------------------------------
	def OnRotateClockwise(self, e):
		self.Tabs.GetCurrentPage().OnRotateClockwise( e )
		self.UpdateTitle()
	
	# -------------------------------------------------------------------
	def OnRotateCounterClockwise(self, e):
		self.Tabs.GetCurrentPage().OnRotateCounterClockwise( e )
		self.UpdateTitle()
			
	# -------------------------------------------------------------------
	def OnOpen(self, e):
		self.Tabs.GetCurrentPage().OnOpen( e )
		self.UpdateSideBar()
		self.UpdateTitle()
	
	# -------------------------------------------------------------------
	def OnSave(self, e):
		self.Tabs.GetCurrentPage().OnSave( e )
		self.Tabs.SetPageText( self.Tabs.GetSelection(), 
													os.path.basename( self.Tabs.GetCurrentPage().CurrentFile ) )
		self.UpdateTitle()
	
	# -------------------------------------------------------------------
	def OnSaveAs(self, e):
		self.Tabs.GetCurrentPage().OnSaveAs( e )
		self.UpdateTitle()
					
	# -------------------------------------------------------------------
	def ProcessCommand(self, e):
		self.Tabs.GetCurrentPage().ProcessCommand( e.GetId() )
	
	# -------------------------------------------------------------------
	def OnTabChange(self, e):
		if e.GetId() == self.Tabs.GetId():
			self.UpdateSideBar()
	
	# -------------------------------------------------------------------
	def UpdateSideBar(self):
		colorctrl = self.SideBar.GetPage(0)
		colorctrl.SketchCtrl = self.Tabs.GetCurrentPage()
		colorctrl.Refresh()
	
	# -------------------------------------------------------------------
	def UpdateTitle(self):
		modified = ''
		
		if self.Tabs.GetCurrentPage().Modified:
			modified = '*'
		
		currentfile = self.Tabs.GetCurrentPage().CurrentFile
		
		if not currentfile:
			self.Tabs.SetPageText( self.Tabs.GetSelection(), 'Untitled' )
			self.SetTitle( APP_NAME )
			return
		
		self.Tabs.SetPageText( self.Tabs.GetSelection(), 
												'%s %s' % ( os.path.basename( currentfile ) ,
																		modified )
												)
		self.SetTitle( '%s - %s %s' % (APP_NAME, currentfile, modified) )

# =================================================================			
def Run():
	wx.InitAllImageHandlers()
	app = wx.PySimpleApp()
	frame = MainWnd(None, -1, APP_NAME)
	frame.Show(1)
	app.MainLoop()

# =================================================================			
if __name__ == '__main__':
	Run()
	#d = Design()
	#d.Load('the.end.2.dst')
	
