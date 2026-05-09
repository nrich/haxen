# haxen
Neil's hacking hex viewer

## Usage

**haxen** *</path/to/file>*

## Commands
| Key | Description |
|---|---|
| h | Open help window |
| TAB | Switch between HEX and ASCII mode |
| ENTER | Jump to absolute file postion |
| PGUP | Jump back one screen of data |
| PGDN | Jump forward one screen of data |
| / | Search for bytes in HEX mode, or string in ASCII mode |
| j | Set $JUMP_OFFSET count (as decimal) |
| J | Set $JUMP_OFFSET count (as hex) |
| SPACE | Jump forward $JUMP_OFFSET bytes |
| m | Create new file make at current cursor position |
| M | Remove last created file mark |
| n | Jump to next file mark |
| N | Jump to previous file mark |
| l | Toggle between little and big endian display mode |
| c | Cycle between character encoding (ASCII, EBCDIC) |
| C | Cycle between archaic character encoding (SQUOZE, RADIX 50, DEC 6BIT) |
| s| Set struct eval pattern $STRUCT |
| \[ | Jump forward sizeof($STRUCT) bytes |
| \] | Jump backward sizeof($STRUCT) bytes |
| < | Jump to first byte of file |
| > | Jump to last byte of file |
| q | Quit |
