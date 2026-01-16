import re

from info import Info, State, MobjInfo

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
            return (None, None)

        prop_name  = tokens[1].strip()
        if prop_name == 'spawnhealth':
            prop_name = 'health'

        prop_value = tokens[0].strip()
        if prop_value.endswith(','):
            prop_value = prop_value[:-1]
            if prop_value == 'S_NULL':
                prop_value = None

        return (prop_name, prop_value)

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

                mobj = MobjInfo(mobj_name, {}, False)

            else:
                # Parsing mobj properties
                brace = line.strip()
                if brace == '},' or brace == '}':
                    mobjs.append(mobj)
                    mobj = None

                else:
                    prop_name, prop_value = self.parse_mobjinfo_property(line)
                    if prop_name and prop_value:
                        mobj.props[prop_name] = prop_value

        return mobjs
