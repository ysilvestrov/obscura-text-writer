"""Bounded local image decoding; Pillow is optional for non-cover operations."""
import io
import warnings

MAX_BYTES=10*1024*1024
MAX_PIXELS=20000000


def image_info(content: bytes, *, normalize=False):
    if not content or len(content)>MAX_BYTES:raise ValueError('Обкладинка має бути до 10 MiB')
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        raise ValueError('Для обкладинок установіть storygen[publication] (Pillow)') from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                if source.format not in {'PNG','JPEG'} or getattr(source,'n_frames',1)!=1:
                    raise ValueError('Потрібне статичне PNG або JPEG зображення')
                if source.width*source.height>MAX_PIXELS:raise ValueError('Обкладинка має бути до 20 мільйонів пікселів')
                source.load()
                fmt=source.format
                if not normalize:return ('image/png' if fmt=='PNG' else 'image/jpeg',source.width,source.height)
                image=ImageOps.exif_transpose(source)
                mode='RGBA' if fmt=='PNG' and (image.mode in {'RGBA','LA'} or 'transparency' in image.info) else 'RGB'
                # Copy pixels into a new image: no EXIF, GPS, ICC, comments or text chunks.
                clean=Image.new(mode,image.size)
                clean.paste(image.convert(mode))
                output=io.BytesIO()
                clean.save(output,format=fmt,**({'quality':95} if fmt=='JPEG' else {}))
                result=output.getvalue()
                if len(result)>MAX_BYTES:raise ValueError('Нормалізована обкладинка перевищує 10 MiB')
                return result,('image/png' if fmt=='PNG' else 'image/jpeg'),clean.width,clean.height
    except (UnidentifiedImageError,OSError,SyntaxError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ValueError('Не вдалося прочитати безпечне PNG/JPEG зображення') from None
