"""Texture converter.

Notes:
    You need to build dll from https://github.com/matyalatte/Texconv-Custom-DLL.
    And put the dll in the same directory as texconv.py.
"""
import ctypes
import os

from .dds import DDSHeader, DXGI_FORMAT, is_hdr, disassemble_cubemap
from . import util


class Texconv:
    """Texture converter."""
    def __init__(self, dll_path=None):
        """Constructor."""
        if dll_path is None:
            file_path = os.path.realpath(__file__)
            if util.is_windows():
                dll_path = os.path.join(os.path.dirname(file_path), "texconv.dll")
            elif util.is_mac():
                dll_path = os.path.join(os.path.dirname(file_path), "libtexconv.dylib")
            elif util.is_linux():
                dll_path = os.path.join(os.path.dirname(file_path), "libtexconv.so")
            else:
                raise RuntimeError(f'This OS ({util.get_os_name()}) is unsupported.')

        dll_path = os.path.abspath(dll_path)

        if not os.path.exists(dll_path):
            raise RuntimeError(f'texconv not found. ({dll_path})')

        self.dll = ctypes.cdll.LoadLibrary(dll_path)

    def run(self, args, verbose=True, allow_slow_codec=False):
        """Run texconv with args."""
        args_p = [ctypes.c_wchar_p(arg) for arg in args]
        args_p = (ctypes.c_wchar_p*len(args_p))(*args_p)
        err_buf = ctypes.create_unicode_buffer(512)
        result = self.dll.texconv(len(args), args_p, verbose, False, allow_slow_codec, err_buf, 512)
        if result != 0:
            raise RuntimeError(err_buf.value)

    def convert(self, file, args, out=None, verbose=True, allow_slow_codec=False):
        """Convert a texture with args."""
        if out is not None and isinstance(out, str):
            args += ['-o', out]
        else:
            out = '.'

        if out not in ['.', ''] and not os.path.exists(out):
            util.mkdir(out)

        args += ["-y"]
        args += [os.path.normpath(file)]
        self.run(args, verbose=verbose, allow_slow_codec=allow_slow_codec)
        return out

    def convert_to_tga(self, file, out=None, invert_normals=False, cubemap_suffix="AXIS", verbose=True):
        """Convert dds to tga."""
        dds_header = DDSHeader.read_from_file(file)
        print(f'DXGI_FORMAT: {dds_header.get_format_as_str()[12:]}')

        if dds_header.is_3d():
            raise RuntimeError('Can not convert 3D textures with texconv.')

        if dds_header.is_cube():
            new_file_names = disassemble_cubemap(file, out_dir=out, cubemap_suffix=cubemap_suffix)
            tga_names = []
            for file_name in new_file_names:
                tga_names.append(self.convert_to_tga(file_name, out=out,
                                                     invert_normals=invert_normals, verbose=verbose))
            return tga_names

        args = []

        if dds_header.is_hdr():
            fmt = 'hdr'
            if not dds_header.convertible_to_hdr():
                args += ['-f', 'fp32']
        else:
            fmt = 'tga'
            if not dds_header.convertible_to_tga():
                args += ['-f', 'rgba']

        if dds_header.is_int():
            msg = f'Int format detected. ({dds_header.get_format_as_str()})\n It might not be converted correctly.'
            raise RuntimeError(msg)

        args += ['-ft', fmt]

        if dds_header.is_bc5():
            args += ['-reconstructz']
            if invert_normals:
                args += ['-inverty']

        out = self.convert(file, args, out=out, verbose=verbose)
        name = os.path.join(out, os.path.basename(file))
        name = '.'.join(name.split('.')[:-1] + [fmt])
        return name

    def convert_to_dds(self, file, dds_fmt, out=None,
                       invert_normals=False, no_mip=False, verbose=True, allow_slow_codec=False):
        """Convert texture to dds."""
        if not DXGI_FORMAT.is_valid_format("DXGI_FORMAT_" + dds_fmt):
            raise RuntimeError(f'Not DXGI format. ({dds_fmt})')
        if is_hdr(dds_fmt) and file[-3:].lower() != 'hdr':
            raise RuntimeError(f'Use .hdr for HDR textures. ({file})')
        if ('BC6' in dds_fmt or 'BC7' in dds_fmt) and (not util.is_windows()) and (not allow_slow_codec):
            raise RuntimeError(f'Can NOT use CPU codec for {dds_fmt}. Or enable the "Allow Slow Codec" option.')

        print(f'DXGI_FORMAT: {dds_fmt}')
        args = ['-f', dds_fmt]
        if no_mip:
            args += ['-m', '1']
        out = self.convert(file, args, out=out, verbose=verbose, allow_slow_codec=allow_slow_codec)
        name = os.path.join(out, os.path.basename(file))
        name = '.'.join(name.split('.')[:-1] + ['dds'])
        return name
