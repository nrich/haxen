#!/usr/bin/env python

"""Neil's hacking hex viewer"""

# pylint: disable=C0103,C0301,W0702,W0703,W1202,W1203

import argparse
import curses
import datetime
import logging
import mmap
import os.path
import string
import struct
import textwrap
from curses import wrapper,textpad
from typing import Dict,List,Tuple

logger = logging.getLogger(__name__)

def _buffer_as_hex(buffer: bytes, no_spaces: bool = False) -> str:
    """Util to convert buffer to human friendly format."""

    if no_spaces:
        return "".join([f'{b & 0xff:02X}' for b in list(buffer)])

    return " ".join([f'{b & 0xff:02X}' for b in list(buffer)])

def _buffer_as_spaced_hex(buffer: bytes) -> str:
    chunks: List[str] = []

    for i in range(0, len(buffer), 4):
        chunks.append(" ".join([f'{b & 0xff:02X}' for b in list(buffer[i:i+4])]))


    return "  ".join(chunks)    

def _buffer_as_print(buffer: bytes) -> str:
    allowed = bytearray(b'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ ')

    return "".join([chr(b) if b in allowed else '.' for b in list(buffer)])

def _index_to_position(idx: int, bytes_per_line: int, left_offset: int) -> Tuple[int, int]:
    y = idx // bytes_per_line
    x = idx % bytes_per_line

    x = x * 3 + (x // 4)

    # skip border
    y += 1

    # add left spacing
    x += left_offset + 3

    return [y, x]


def _index_to_ascii_position(idx: int, bytes_per_line: int, left_offset: int) -> Tuple[int, int]:
    y = idx // bytes_per_line
    x = idx % bytes_per_line

    offset = bytes_per_line * 3 + (bytes_per_line // 4)

    # skip border
    y += 1

    # add left spacing
    x += left_offset + 3 + offset

    return [y, x]


def main(stdscr) -> None:
    """The main entry point."""
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-v', '--verbose', help='Verbose output', action='store_true', dest='verbose')
    argparser.add_argument('-q', '--quiet', help='Quiet output', action='store_true', dest='quiet')
    argparser.add_argument('-d', '--debug', help='Debug mode', action='store_true', dest='quiet')
    argparser.add_argument('binfile', help='Input binary file', type=str)
    args = argparser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='[%(process)d] (%(funcName)s) %(message)s')
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR, format='')
    else:
        logging.basicConfig(level=logging.INFO, format='[%(process)d] (%(funcName)s) %(message)s')

    stdscr.clear()
    height, width = stdscr.getmaxyx()

    #stdscr.border()
    #stdscr.addstr(0, width>>1, os.path.basename(args.binfile))

    data_win_width: int = 42
    data_win_height: int = (height // 3)

    dump_win_width: int = (width - data_win_width)
    dump_win_height: int = height

    mark_win_width: int = 42
    mark_win_height: int = (height // 3)

    eval_win_width: int = 42
    eval_win_height: int = (height // 3)

    # newwin(height, width, begin_y, begin_x)
    dump_win = curses.newwin(dump_win_height, dump_win_width, 0, 0)
    dump_win.box() # Uses default characters

    data_win = curses.newwin(data_win_height, data_win_width, 0, dump_win_width+0)

    mark_win = curses.newwin(mark_win_height, mark_win_width, data_win_height, dump_win_width+0)
    mark_win.box()
    mark_win.addstr(0, (mark_win_width>>1) - 4, f'File marks')

    eval_win = curses.newwin(eval_win_height, eval_win_width, data_win_height+mark_win_height, dump_win_width+0)
    eval_win.box()
    eval_win.addstr(0, (eval_win_width>>1) - 4, f'Eval')

    # Refresh to display changes
    stdscr.refresh()
    dump_win.refresh()
    data_win.refresh()
    mark_win.refresh()
    eval_win.refresh()

    #dump_win.addstr(0, dump_win_width + (data_win_width>>1), "Eval")


    file_size: int = os.path.getsize(args.binfile)

    if file_size > 2**32:
        offset_address_size: int = 12
    else:
        offset_address_size: int = 8

    bytes_per_line: int = (dump_win_width - offset_address_size) // 4
    cy,_ =  _index_to_position(bytes_per_line, bytes_per_line, offset_address_size)
    if cy > 1:
        bytes_per_line -= 4
    bytes_per_line -= (bytes_per_line % 4)

    hex_offset = offset_address_size + 3
    ascii_offset = (bytes_per_line * 3 + (bytes_per_line // 4)) + hex_offset

    #raise ValueError((bytes_per_line, hex_offset, ascii_offset, _index_to_position(31, bytes_per_line, offset_address_size))) 

    cursor_position = 0

    file_offset = 0

    modes = [
        'hex',
        'ascii',
    ]

    mode = 0
    byteorder = 'little'

    jump_offset: int = 0

    ascii_search: str = ''
    hex_search: str = b''
    struct_eval: str = ''

    marks: List[int] = []

    with open(args.binfile, 'rb+') as fh:
        with mmap.mmap(fh.fileno(), length=0, access=mmap.ACCESS_WRITE) as fm:
            while True:
                data_offset: int = file_offset + cursor_position

                dump_win.box() # Uses default characters
                dump_win.addstr(0, dump_win_width>>1, os.path.basename(args.binfile))
                dump_win.addstr(dump_win_height-1, 4, f' 0x{data_offset:X}/0x{file_size:X}  {int((data_offset)/file_size * 100):3d}%')

                data_win.box()
                data_win.addstr(0, (data_win_width>>1) - 4, f'Data ({byteorder})')

                if mode == 1:
                    cy, cx = _index_to_ascii_position(cursor_position, bytes_per_line, offset_address_size)
                else:
                    cy, cx = _index_to_position(cursor_position, bytes_per_line, offset_address_size)

                stdscr.move(cy, cx)
                cy, cx = stdscr.getyx()

                data_line_length = (bytes_per_line * 3) + (bytes_per_line // 4)

                for i in range(0, dump_win_height-2):
                    offset: int = i * bytes_per_line + file_offset

                    hex_data = fm[offset:offset+bytes_per_line]

                    dump_win.addstr(i+1, 1, f'{offset:0{offset_address_size}X}  {_buffer_as_spaced_hex(hex_data)}')
                    dump_win.addstr(i+1, data_line_length+offset_address_size+3, f'{_buffer_as_print(hex_data)}')

                screen_start_offset: int = file_offset
                bytes_per_screen: int = bytes_per_line * (dump_win_height-2)

                int8 = int.from_bytes(fm[data_offset:data_offset+1], byteorder=byteorder, signed=True)
                uint8 = int.from_bytes(fm[data_offset:data_offset+1], byteorder=byteorder, signed=False)
                int16 = int.from_bytes(fm[data_offset:data_offset+2], byteorder=byteorder, signed=True)
                uint16 = int.from_bytes(fm[data_offset:data_offset+2], byteorder=byteorder, signed=False)
                int32 = int.from_bytes(fm[data_offset:data_offset+4], byteorder=byteorder, signed=True)
                uint32 = int.from_bytes(fm[data_offset:data_offset+4], byteorder=byteorder, signed=False)
                int64 = int.from_bytes(fm[data_offset:data_offset+8], byteorder=byteorder, signed=True)
                uint64 = int.from_bytes(fm[data_offset:data_offset+8], byteorder=byteorder, signed=False)
                #[f32] = struct.unpack('f', fm[data_offset:data_offset+4])
                #[f64] = struct.unpack('d', fm[data_offset:data_offset+8])


                data_win.addstr(1, 1, f'INT8    {int8:>32d}')
                data_win.addstr(2, 1, f'UINT8   {uint8:>32d}')
                data_win.addstr(3, 1, f'INT16   {int16:>32d}')
                data_win.addstr(4, 1, f'UINT16  {uint16:>32d}')
                data_win.addstr(5, 1, f'INT32   {int32:>32d}')
                data_win.addstr(6, 1, f'UINT32  {uint32:>32d}')
                data_win.addstr(7, 1, f'INT64   {int64:>32d}')
                data_win.addstr(8, 1, f'UINT64  {uint64:>32d}')
                data_win.addstr(9, 1, f'EPOCH   {datetime.datetime.fromtimestamp(uint32).strftime("%c"):>32}')

                #data_win.addstr(9, 1, f'F32     {f32:1.10f}')
                #data_win.addstr(10, 1, f'F64     {str(f64)[:20]}')


                mark_win.box()
                mark_win.addstr(0, (mark_win_width>>1) - 4, f'File marks')
                for i,mark in enumerate(marks):
                    mark_win.addstr(1+i, 1, f'0x{mark:012X}    {(data_offset-mark):22d}')

                if struct_eval:
                    real_position: int = file_offset + cursor_position
                    eval_size = struct.calcsize(struct_eval)
                    try:
                        eval_data = struct.unpack(struct_eval, fm[real_position:real_position+eval_size])
                        for i,data in enumerate(eval_data):
                            if isinstance(data, bytes):
                                eval_win.addstr(2+i, 1, f'{i:<3d} {_buffer_as_print(data)}')
                            else:
                                eval_win.addstr(2+i, 1, f'{i:<3d} {str(data)}')
                    except:
                        eval_win.addstr(2, 1, f'*Error*')

                data_win.refresh()
                dump_win.refresh()
                mark_win.refresh()
                eval_win.refresh()
                stdscr.refresh()

                keypress = stdscr.getch()
                if keypress == curses.KEY_DOWN:
                    # down
                    if cy > (dump_win_height-3):
                        file_offset += bytes_per_line
                    else:
                        cursor_position += bytes_per_line
                elif keypress == curses.KEY_UP:
                    # up

                    if cy < 2:
                        file_offset -= bytes_per_line
                    else:
                        cursor_position -= bytes_per_line
                elif keypress == curses.KEY_LEFT:
                    # left
                    cursor_position -= 1
                    if cy < 2:
                        if mode == 0:
                            if cx <= hex_offset:
                                file_offset -= bytes_per_line
                                cursor_position += bytes_per_line
                        else:
                            if cx <= ascii_offset:
                                file_offset -= bytes_per_line
                                cursor_position += bytes_per_line
                elif keypress == curses.KEY_RIGHT:
                    # right
                    cursor_position += 1
                    if cy > (dump_win_height-3):
                        if mode == 0:
                            if cx >= ascii_offset - 4:
                                file_offset += bytes_per_line
                                cursor_position -= bytes_per_line
                        else:
                            if cx > ascii_offset + bytes_per_line - 2:
                                file_offset += bytes_per_line
                                cursor_position -= bytes_per_line

                elif keypress == 9:
                    # switch window
                    mode += 1
                    mode %= len(modes)
                elif keypress == curses.KEY_NPAGE:
                    # next screen
                    file_offset += bytes_per_screen
                    dump_win.clear()
                elif keypress == curses.KEY_PPAGE:
                    # previous screen
                    file_offset -= bytes_per_screen
                    dump_win.clear()
                elif keypress in [44, 60]:
                    # jump to start
                    cursor_position = 0
                    file_offset = 0
                    dump_win.clear()
                elif keypress in [46, 62]:
                    # jump to end
                    file_offset = file_size // (bytes_per_line * dump_win_height-2) * (bytes_per_line * dump_win_height-2)
                    cursor_position = file_size % (bytes_per_line * dump_win_height-2)
                    cursor_position -= 1
                    dump_win.clear()
                elif keypress == 10:
                    # Jump to position
                    jump_win = curses.newwin(3, 60, dump_win_height//2 - 1, dump_win_width//2 - 30)
                    jump_win.box()
                    jump_win.addstr(0, 22, "Jump to position")
                    jump_win.addstr(1, 2, "0x")
                    jump_win.refresh()

                    curses.echo()
                    location = jump_win.getstr()
                    curses.noecho()

                    try:
                        jump_location = int(location, 16)

                        if jump_location > file_size:
                            raise ValueError('Invalid jump location')

                        cursor_position = jump_location % bytes_per_screen
                        file_offset = (jump_location // bytes_per_screen) * bytes_per_screen
                    except:
                        pass
                elif keypress == 106:
                    # set jump
                    jump_win = curses.newwin(3, 60, dump_win_height//2 - 1, dump_win_width//2 - 30)
                    jump_win.box()
                    jump_win.addstr(0, 22, "Set Jump Offset")
                    jump_win.addstr(1, 2, "")
                    jump_win.refresh()

                    curses.echo()
                    location = jump_win.getstr()
                    curses.noecho()

                    try:
                        jump_offset = int(location, 10)
                    except:
                        jump_offset = 0
                elif keypress == 74:
                    # set jump
                    jump_win = curses.newwin(3, 60, dump_win_height//2 - 1, dump_win_width//2 - 30)
                    jump_win.box()
                    jump_win.addstr(0, 22, "Set Jump Offset")
                    jump_win.addstr(1, 2, "0x")
                    jump_win.refresh()

                    curses.echo()
                    location = jump_win.getstr()
                    curses.noecho()

                    try:
                        jump_offset = int(location, 16)
                    except:
                        jump_offset = 0
                elif keypress == 32:
                    # repeat jump
                    try:
                        real_position: int = file_offset + cursor_position + jump_offset
                        cursor_position = real_position % bytes_per_screen
                        file_offset = (real_position // bytes_per_screen) * bytes_per_screen
                    except:
                        pass
                elif keypress == 47:
                    # search
                    pass

                    if mode == 1:
                        search_win = curses.newwin(3, 60, dump_win_height//2 - 1, dump_win_width//2 - 30)
                        search_win.box()
                        search_win.addstr(0, 19, "ASCII string to search")
                        search_win.addstr(1, 2, "")
                        search_win.refresh()

                        curses.echo()
                        new_ascii_search = search_win.getstr()
                        if new_ascii_search:
                            ascii_search = new_ascii_search
                        curses.noecho()

                        real_position: int = file_offset + cursor_position + jump_offset
                        new_position = fm.find(ascii_search, real_position+1) 
                        if ascii_search and new_position != -1:
                            cursor_position = new_position % bytes_per_screen
                            file_offset = (new_position // bytes_per_screen) * bytes_per_screen
                    else:
                        search_win = curses.newwin(3, 60, dump_win_height//2 - 1, dump_win_width//2 - 30)
                        search_win.box()
                        search_win.addstr(0, 20, "Hex value to search")
                        search_win.addstr(1, 2, "0x")
                        search_win.refresh()

                        curses.echo()
                        new_hex_search = search_win.getstr()
                        if new_hex_search:
                            try:
                                hex_search = bytes.fromhex(new_hex_search.decode('ascii'))
                            except:
                                hex_search = b''
                        curses.noecho()

                        real_position: int = file_offset + cursor_position + jump_offset
                        new_position = fm.find(hex_search, real_position+1) 
                        if hex_search and new_position != -1:
                            cursor_position = new_position % bytes_per_screen
                            file_offset = (new_position // bytes_per_screen) * bytes_per_screen

                elif keypress == 108:
                    byteorder = 'little' if byteorder == 'big' else 'big'
                elif keypress == 109:
                    # add file mark
                    data_offset: int = file_offset + cursor_position

                    if data_offset not in marks:
                        marks.append(data_offset)

                        while len(marks) > 10:
                            marks.pop(0)
                elif keypress == 77:
                    # remove last file mark
                    if marks:
                        marks.pop()
                    mark_win.clear()
                elif keypress == 67:
                    # jump to previous mark
                    if marks:
                        real_position: int = file_offset + cursor_position + jump_offset
                        next_positions: int = [mark for mark in marks if mark < real_position]

                        new_position: int = next_positions[-1] if next_positions else marks[-1]

                        cursor_position = new_position % bytes_per_screen
                        file_offset = (new_position // bytes_per_screen) * bytes_per_screen

                elif keypress == 99:
                    # jump to next mark
                    if marks:
                        real_position: int = file_offset + cursor_position + jump_offset
                        next_positions: int = [mark for mark in marks if mark > real_position]

                        new_position: int = next_positions[0] if next_positions else marks[0]

                        cursor_position = new_position % bytes_per_screen
                        file_offset = (new_position // bytes_per_screen) * bytes_per_screen
                elif keypress == 104:
                    # struct eval
                    struct_win = curses.newwin(3, 60, dump_win_height//2 - 1, dump_win_width//2 - 30)
                    struct_win.box()
                    struct_win.addstr(1, 2, struct_eval)
                    char = struct_win.getch()
                    while char != 10:
                        if char == 127:
                            if struct_eval:
                                struct_eval = struct_eval[:-1]
                        else:
                            struct_eval += chr(char)
                        struct_win.addstr(1, 2 + len(struct_eval), ' ')
                        struct_win.addstr(1, 2, struct_eval)
                        char = struct_win.getch()

                    if struct_eval:
                        eval_win.addstr(1, 1, f'{struct_eval}  len={(struct.calcsize(struct_eval))}')
                elif keypress == 72:
                    # jump struct eval number of bytes
                    if struct_eval:
                        real_position: int = file_offset + cursor_position + jump_offset
                        new_position: int = real_position + struct.calcsize(struct_eval)
                        if new_position < file_size:
                            cursor_position = new_position % bytes_per_screen
                            file_offset = (new_position // bytes_per_screen) * bytes_per_screen
                elif keypress == 410:
                    # window resize
                    pass
                else:
                    if args.debug:
                        raise ValueError(keypress)

                cursor_position = max(cursor_position, 0)
                cursor_position = min(cursor_position, file_size)
                file_offset = max(file_offset, 0)
                file_offset = min(file_offset, file_size - (file_size % (bytes_per_line * dump_win_height-2)))


if __name__ == "__main__":
    wrapper(main)
