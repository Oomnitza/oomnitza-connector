import wx


class Image(wx.StaticBitmap):

    def __init__(self, parent=None, file_path="",
                 width_scale=1, height_scale=1):
        image = wx.Image(file_path, wx.BITMAP_TYPE_ANY)

        image_width = image.GetWidth()
        image_height = image.GetHeight()

        image = image.Scale(image_width / width_scale,
                            image_height / height_scale)

        wx.StaticBitmap.__init__(self, parent, -1, wx.BitmapFromImage(image))