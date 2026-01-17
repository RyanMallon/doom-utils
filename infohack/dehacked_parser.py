import re

from info import Info, State, MobjInfo

class DehackedParser:
    def __init__(self, lines, patch):
        self.lines = lines
        self.patch = patch

    def get_line(self):
        return self.lines[0].strip()

    def consume_line(self):
        return self.lines.pop(0).strip()

    def parse_prop_list(self, obj):
        while True:
            line = self.consume_line()
            if line == '':
                break

            prop = line.split('=')
            prop = [p.strip() for p in prop]
            obj[prop[0]] = prop[1]

    def parse_thing(self):
        line = self.consume_line()
        m = re.match(r'Thing ([0-9]+) \(([^)]+)\)', line)
        if not m:
            raise Exception('Bad thing: {}'.format(line))

        thing = {}
        thing_num = int(m.group(1))
        thing['alias'] = m.group(2)

        self.parse_prop_list(thing)
        self.patch.things[thing_num] = thing

    def parse_frame(self):
        line = self.consume_line()
        m = re.match('Frame ([0-9]+)', line)
        if not m:
            raise Exception('Bad frame: {}'.format(line))

        frame = {}
        frame_num = int(m.group(1))

        self.parse_prop_list(frame)
        self.patch.frames[frame_num] = frame

    def parse_pointer(self):
        line = self.consume_line()
        m = re.match(r'Pointer ([0-9]+) \(Frame ([0-9]+)\)', line)
        if not m:
            raise Exception('Bad pointer: {}'.format(line))

        src_frame_index = int(m.group(2))

        line = self.consume_line()
        m = re.match(r'Codep Frame = ([0-9]+)', line)
        if not m:
            raise Exception('Bad pointer: {}'.format(line))

        dst_frame_index = int(m.group(1))

        self.patch.pointers.append((src_frame_index, dst_frame_index))

    def parse_codeptr(self):
        self.consume_line()
        while True:
            line = self.consume_line()
            if line == '':
                break

            prop = line.split('=')
            prop = [p.strip() for p in prop]

            frame_num = int(prop[0].split(' ')[1])
            if prop[1] == 'NULL':
                self.patch.codeptrs[frame_num] = None
            else:
                self.patch.codeptrs[frame_num] = prop[1]

    def parse(self):
        parsers = {
            'Thing'     : self.parse_thing,
            'Frame'     : self.parse_frame,
            'Pointer'   : self.parse_pointer,
            '[CODEPTR]' : self.parse_codeptr,
        }

        while len(self.lines):
            line = self.get_line()

            if line.startswith('#') or line == '':
                # Skip comments/blank lines
                self.consume_line()
                continue

            parsed = False
            for k, v in parsers.items():
                if line.startswith(k):
                    v()
                    parsed = True
                    break

            if not parsed:
                self.consume_line()
