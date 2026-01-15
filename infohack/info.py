from collections import namedtuple
import sys
import re

State = namedtuple('State', 'sprite frame tics action nextstate misc1 misc2 name')
Property = namedtuple('Property', 'name value')
MobjInfo = namedtuple('MobjInfo', 'name props')

class Info:
    state_names = [
        'spawn',
        'see',
        'run',

        'melee',
        'missile',
        'refire',

        'crash',	# Heretic/Hexen

        'pain',
        'death',
        'xdeath',

        'raise',
    ]

    def __init__(self):
        self.states = []
        self.mobjs  = []

    def get_state_by_name(self, name):
        states = [s for s in self.states if s.name == name]
        if len(states) == 0:
            return None
        if len(states) != 1:
            raise Exception('{} states named {} found'.format(len(states), name))

        return states[0]

    def get_mobj_by_name(self, name):
        mobjs = [m for m in self.mobjs if m.name == name]
        if len(mobjs) == 0:
            return None
        if len(mobjs) != 1:
            raise Exception('{} mobjs named {} found'.format(len(mobjs), name))

        return mobjs[0]

    def get_mobj_first_state(self, mobj, state_name):
        prop = mobj.props.get('{}state'.format(state_name))
        if prop is None:
            return None

        return self.get_state_by_name(prop)

    def mobj_states_are_mergable(self, state_a, state_b):
        if state_a.sprite != state_b.sprite:
            return False

        if (state_a.frame & 0x8000) != (state_b.frame & 0x8000):
            return False

        if state_a.tics != state_b.tics:
            return False

        if state_a.action != state_b.action:
            return False

        return True

class InfoParser:
    def __init__(self, info_filename):
        self.lines = open(info_filename, 'r').readlines()

    def parse(self, info):
        info.states = self.parse_states()
        info.mobjs  = self.parse_mobjinfo()

    def parse_state_line(self, line):
        exp  = r'\s*\{([A-Z]{3}_[A-Z0-9]{4}),\s*'	# Sprite
        exp += r'([-0-9]+),\s*'				# Frame
        exp += r'([-0-9]+),\s*'				# Tics
        exp += r'\{?([A-Za-z0-9_]+)\}?,\s*'		# Action
        exp += r'([A-Za-z0-9_]+),\s*'			# Next state
        exp += r'([-0-9]+),\s*'				# Misc 1
        exp += r'([-0-9]+)\s*\},?\s*'			# Misc 2
        exp += r'// (.*)$'				# Comment

        m = re.match(exp, line)
        if not m:
            print('Bad state:')
            print(line)
            raise Exception('Bad state')

        sprite    = m.group(1)
        frame     = int(m.group(2), 10)
        tics      = int(m.group(3), 10)
        action    = m.group(4)
        nextstate = m.group(5)
        misc1     = int(m.group(6), 10)
        misc2     = int(m.group(7), 10)
        name      = m.group(8)

        if action == 'NULL':
            action = None
        if nextstate == 'S_NULL':
            nextstate = None

        return State(sprite, frame, tics, action, nextstate, misc1, misc2, name)

    def parse_states(self):
        states = []
        done = False

        for i, line in enumerate(self.lines):
            if done:
                break

            if re.search(r'^state_t\s+states', line):
                for state_line in self.lines[i + 1:]:
                    if state_line.startswith('};'):
                        done = True
                        break

                    state = self.parse_state_line(state_line)
                    states.append(state)

        return states

    def parse_mobjinfo_property(self, line):
        tokens = line.split('//')
        if len(tokens) != 2:
            return None

        prop_name  = tokens[1].strip()
        if prop_name == 'spawnhealth':
            prop_name = 'health'

        prop_value = tokens[0].strip()
        if prop_value.endswith(','):
            prop_value = prop_value[:-1]
            if prop_value == 'S_NULL':
                prop_value = None

        return Property(prop_name, prop_value)

    def parse_mobjinfo(self):
        found_start = False
        mobj = None
        mobjs = []

        for line in self.lines:
            if not found_start:
                if line.startswith('mobjinfo_t'):
                    found_start = True

            elif mobj is None:
                # Find the start of a mobj definition
                tokens = line.split('//')
                if len(tokens) != 2:
                    continue

                brace     = tokens[0].strip()
                mobj_name = tokens[1].strip()
                if brace != '{' or not mobj_name.startswith('MT_'):
                    continue

                mobj = MobjInfo(mobj_name, {})

            else:
                # Parsing mobj properties
                brace = line.strip()
                if brace == '},' or brace == '}':
                    mobjs.append(mobj)
                    mobj = None

                else:
                    prop = self.parse_mobjinfo_property(line)
                    if prop:
                        mobj.props[prop.name] = prop.value

        return mobjs

class DecohackWriter:
    def __init__(self, info):
        self.info = info

        self.indent_level = 0
        self.spacer = False

    def output(self, fmt):
        line  = '\t' * self.indent_level
        line += fmt

        print(line)
        self.spacer = True

    def indent(self, string):
        if string is not None:
            self.output(string)

        self.indent_level += 1

    def unindent(self, string):
        if self.indent_level == 0:
            raise Exception('Indent level underflow')

        self.indent_level -= 1
        if string is not None:
            self.output(string)

    def output_spacer(self):
        if self.spacer:
            self.output('')

        self.spacer = False

    def output_mobj_props(self, mobj):
        prop_names = [
            'health',
            'speed',
            'radius',
            'height',
            'damage',
            'reactiontime',
            'painchance',
            'mass',
        ]

        for name in prop_names:
            value = mobj.props.get(name)
            if value is not None:
                value = re.sub(r'\s*\*\s*FRACUNIT$', '', value)
                if value == 'FRACUNIT':
                    value = '1'

                self.output('{} {}'.format(name, value))

        self.output_spacer()

    def output_mobj_sounds(self, mobj):
        sound_names = [
            'seesound',
            'attacksound',
            'painsound',
            'deathsound',
            'activesound',
        ]
        no_sound = [
            '0',
            'sfx_None',
            'SFX_NONE',
        ]

        for sound in sound_names:
            value = mobj.props.get(sound)
            if value is not None:
                value = mobj.props[sound]
                if value not in no_sound:
                    value = re.sub(r'^sfx_', '', value)

                    self.output('{} "{}"'.format(sound, value))

        self.output_spacer()

    def output_mobj_flags(self, mobj):
        flags = []

        for flag_prop_name in ['flags', 'flags2']:
            flag_prop = mobj.props.get(flag_prop_name)
            if flag_prop is not None:
                flags.extend(flag_prop.split('|'))

        flags = [f.strip() for f in flags]
        flags = [re.sub(r'^MF2?_', '', f) for f in flags]
        if '0' in flags:
            flags.remove('0')

        self.output('clear flags')
        for flag in flags:
            self.output('+{}'.format(flag))

        self.output_spacer()

    def build_mobj_state_machine(self, mobj, state_name):
        goto = None

        items = []

        state = self.info.get_mobj_first_state(mobj, state_name)

        while state is not None:
            items.append(state)
            try:
                next_state = info.get_state_by_name(state.nextstate)
            except:
                next_state = None

            # Has this state looped/jumped to the start of another state
            if next_state is not None:
                for other_state_name in Info.state_names:
                    if next_state == self.info.get_mobj_first_state(mobj, other_state_name):
                        goto = other_state_name
                        next_state = None
                        break

            # Check for loop back to non-starting state
            if next_state is not None and len(items) > 1:
                for i, other_state in enumerate(items[1:]):
                    if next_state == other_state:
                        # Create a new state
                        if state_name == 'missile':
                            new_state_name = 'refire'
                        elif state_name == 'see':
                            new_state_name = 'run'
                        else:
                            new_state_name = '{}_2'.format(state_name)

                        items = items[0:i + 1]
                        mobj.props['{}state'.format(new_state_name)] = state.nextstate

                        goto = 'continue'
                        next_state = None
                        break

            state = next_state

        return items, goto

    def merge_mobj_states(self, states):
        prev_state = None
        new_states = []
        merged = []

        for state in states:
            if not prev_state or not self.info.mobj_states_are_mergable(state, prev_state):
                if len(merged) > 0:
                    new_states.append(merged)

                merged = []

            merged.append(state)
            prev_state = state

        if len(merged) > 0:
            new_states.append(merged)

        return new_states

    def merged_mobj_state_to_decohack(self, merged):
        state = merged[0]
        string = ''

        string += '{} '.format(state.sprite[4:])

        for m in merged:
            string += '{}'.format(chr(ord('A') + (m.frame & 0x7fff)))

        string += ' {}'.format(state.tics)

        if state.frame & 0x8000:
            string += ' bright'

        if state.action:
            string += ' {}'.format(state.action)

        return string

    def output_mobj_states(self, mobj):
        self.output('states')
        self.indent('{')

        for state_name in Info.state_names:
            state_steps = []
            state_loop  = False

            items, goto = self.build_mobj_state_machine(mobj, state_name)
            if len(items) == 0:
                continue

            prev_item = None

            self.output('{}:'.format(state_name))
            self.indent(None)

            # Many mobjs have combined melee/missile states
            if state_name == 'melee' and self.info.get_mobj_first_state(mobj, 'melee') == self.info.get_mobj_first_state(mobj, 'missile'):
                self.unindent(None)
                continue

            for m in self.merge_mobj_states(items):
                self.output(self.merged_mobj_state_to_decohack(m))

            if goto is not None:
                if goto == state_name:
                    if state_name == 'refire' or state_name == 'run':
                        self.output('goto {}'.format(goto))
                    else:
                        self.output('loop')
                elif goto == 'continue':
                    pass
                else:
                    self.output('stop')

            self.unindent(None)

        self.unindent('}')

    def output_mobj(self, mobj):
        self.output('thing {}'.format(mobj.name))
        self.indent('{')

        self.output_mobj_props(mobj)
        self.output_mobj_sounds(mobj)
        self.output_mobj_flags(mobj)
        self.output_mobj_states(mobj)

        self.unindent('}')

if __name__ == '__main__':
    info_filename = sys.argv[1]

    info = Info()
    info_parser = InfoParser(info_filename)
    info_parser.parse(info)

    writer = DecohackWriter(info)
    writer.output_mobj(info.get_mobj_by_name(sys.argv[2]))
