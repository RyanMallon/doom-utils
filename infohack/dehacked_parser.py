import re

from info import Info, State, MobjInfo

class DehackedParser:
    DEH_INT    = 'deh_int'
    DEH_FIXED  = 'deh_fixed'
    DEH_STRING = 'deh_string'

    def __init__(self, lines):
        self.lines = lines

        self.things = {}
        self.frames = {}
        self.codeptrs = {}

    def log_patch(self, obj, obj_name, obj_prop, old_value, new_value):
        print('Patched {} {}.{}: {} -> {}'.format(obj, obj_name, obj_prop, old_value, new_value))

    def fixed_to_int(self, fixed):
        return int(fixed) >> 16

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
        m = re.match(r'Thing ([0-9]+) \(([^)]+)\)', self.get_line())
        if not m:
            raise Exception('Bad thing: {}'.format(self.get_line()))

        thing = {}
        thing_num = int(m.group(1))
        thing['name'] = m.group(2)

        self.consume_line()
        self.parse_prop_list(thing)
        self.things[thing_num] = thing

    def parse_frame(self):
        m = re.match('Frame ([0-9]+)', self.get_line())
        if not m:
            raise Exception('Bad frame: {}'.format(self.get_line()))

        frame = {}
        frame_num = int(m.group(1))

        self.consume_line()
        self.parse_prop_list(frame)
        self.frames[frame_num] = frame

    def parse_codeptr(self):
        self.consume_line()
        while True:
            line = self.consume_line()
            if line == '':
                break

            prop = line.split('=')
            prop = [p.strip() for p in prop]
            if prop[1] == 'NULL':
                continue

            frame_num = int(prop[0].split(' ')[1])

            self.codeptrs[frame_num] = 'A_{}'.format(prop[1])

    def parse(self):
        parsers = {
            # 'Patch File for DeHackEd'	: self.parse_header,
            'Thing'                     : self.parse_thing,
            'Frame'                     : self.parse_frame,
            '[CODEPTR]'                 : self.parse_codeptr,
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

    def patch_things(self, info):
        prop_dict = {
            'Hit points'     : ('health',     DehackedParser.DEH_INT),
            'Missile damage' : ('damage',     DehackedParser.DEH_INT),
            'Pain chance'    : ('painchance', DehackedParser.DEH_INT),
            'Speed'          : ('speed',      DehackedParser.DEH_INT),
            'Width'          : ('radius',     DehackedParser.DEH_FIXED),
            'Height'         : ('height',     DehackedParser.DEH_FIXED),
        }

        state_dict = {
            'Initial frame'      : 'spawnstate',
            'First moving frame' : 'seestate',
            'Close attack frame' : 'meleestate',
            'Far attack frame'   : 'missilestate',
            'Injury frame'       : 'painstate',
            'Death frame'        : 'deathstate',
            'Exploding frame'    : 'xdeathstate',
            'Respawn frame'      : 'raisestate',
        }

        # TODO: sounds, flags

        for deh_thing_num, deh_thing in self.things.items():
            if deh_thing_num >= len(info.mobjs):
                # TODO: handle extended things
                continue

            thing = info.mobjs[deh_thing_num - 1]

            # Patch properties
            for deh_prop_name, (prop_name, deh_prop_type) in prop_dict.items():
                prop_value = deh_thing.get(deh_prop_name)
                if prop_value:
                    # Convert the value to the correct type if needed
                    if deh_prop_type == DehackedParser.DEH_FIXED:
                        prop_value = self.fixed_to_int(prop_value)

                    self.log_patch('thing', thing.name, prop_name, thing.props[prop_name], prop_value)

                    thing.props[prop_name] = prop_value
                    #thing.modified = True

            # Dechacked stores states as an index.
            # Convert to an entry in the info.states array
            for deh_state_name, state_name in state_dict.items():
                deh_state_index = deh_thing.get(deh_state_name)
                if deh_state_index:
                    try:
                        old_state_name = thing.props[state_name].name
                    except:
                        old_state_name = 'None'

                    new_state = info.states[int(deh_state_index)]
                    self.log_patch('thing', thing.name, state_name, old_state_name, new_state.name)

                    thing.props[state_name] = new_state
                    #thing.modified = True

    def patch_frames(self, info):
        # TODO: mark state/things as modified
        #       need to find all things which use this state

        for deh_frame_num, deh_frame in self.frames.items():
            if deh_frame_num >= len(info.states):
                # TODO: handle extended states
                continue

            state = info.states[deh_frame_num]

            sprite_index = deh_frame.get('Sprite number')
            if sprite_index:
                sprite_name = info.constants.sprite_names[int(sprite_index)]
                state.sprite = 'SPR_{}'.format(sprite_name)

            frame_index = deh_frame.get('Sprite subnumber')
            if frame_index:
                state.frame = int(frame_index)

            nextframe_index = deh_frame.get('Next frame')
            if nextframe_index:
                nextframe_index = int(nextframe_index)
                if nextframe_index >= len(info.states):
                    # TODO: handle extended states
                    continue

                new_nextstate = info.states[int(nextframe_index)]

                self.log_patch('state', state.name, 'nextstate', state.nextstate, new_nextstate.name)

                state.nextstate = new_nextstate

            tics = deh_frame.get('Duration')
            if tics:
                state.tics = int(tics)

    def patch(self, info):
        self.patch_things(info)
        self.patch_frames(info)
