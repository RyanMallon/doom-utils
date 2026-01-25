import re

from info import Info, State, MobjInfo

class StateMachine:
    def __init__(self, info, initial_labels):
        self.info = info
        self.first_states = {**initial_labels}

        # Build the state machine for each label
        self.state_machines = {}
        for label in DecohackWriter.state_names:
            self.build_state_machine_for_label(label)

    def get_first_state(self, label):
        state_name = self.first_states.get(label)
        if not state_name:
            return None

        return self.info.get_state_by_name(state_name)

    def build_state_machine_for_label(self, label):
        retrigger_labels = {
            # Things
            'missile' : 'refire',
            'see'     : 'run',
        }

        goto = None
        states = []

        state = self.get_first_state(label)
        while state is not None:
            states.append(state)
            next_state = self.info.get_state_by_name(state.nextstate)

            # Has this state looped/jumped to the start of another state
            if next_state is not None:
                for other_label in self.first_states.keys():
                    if next_state == self.get_first_state(other_label):
                        if label == other_label and label not in retrigger_labels.values():
                            goto = 'loop'
                        else:
                            goto = 'goto {}'.format(other_label)
                        next_state = None
                        break

            # Check for loop back to non-starting state
            if next_state is not None and len(states) > 1:
                for i, other_state in enumerate(states[1:]):
                    if next_state == other_state:
                        # Create a new label
                        # This will need to be parsed to build its state machine
                        new_label = retrigger_labels.get(label)
                        if not new_label:
                            new_label = '{}_2'.format(state_name)

                        states = states[0:i + 1]
                        self.first_states[new_label] = state.nextstate
                        goto = 'continue'
                        next_state = None
                        break

            state = next_state

        if len(states) > 0:
            self.state_machines[label] = (states, goto)

    def get_duplicate_labels(self, label):
        (states, _) = self.state_machines[label]

        # Note that the returned list includes the current label so will always
        # have a length of at least 1. This is done so that the caller can check
        # if the label is the last in the list of duplicates.
        duplicates = []
        for other_label, (other_states, _) in self.state_machines.items():
            if states[0] == other_states[0]:
                duplicates.append(other_label)

        return duplicates

class DecohackWriter:
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

    weapon_state_names = [
        'select',
        'deselect',
        'ready',
        'fire',
        'flash',
    ]

    def __init__(self, info):
        self.info = info

        self.indent_level = 0
        self.spacer = False

    def output(self, fmt):
        if fmt:
            line  = '\t' * self.indent_level
            line += fmt
        else:
            line = ''

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
                if isinstance(value, str):
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

        for flag in flags:
            self.output('+{}'.format(flag))

        self.output_spacer()

    def merge_states(self, states):
        prev_state = None
        new_states = []
        merged = []

        for state in states:
            if not prev_state or not self.info.states_are_mergable(state, prev_state):
                if len(merged) > 0:
                    new_states.append(merged)

                merged = []

            merged.append(state)
            prev_state = state

        if len(merged) > 0:
            new_states.append(merged)

        return new_states

    def merged_state_to_decohack(self, merged):
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

    def output_state_machine(self, sm):
        for label, (states, goto) in sm.state_machines.items():
            prev_state = None

            self.output('{}:'.format(label))
            self.indent(None)

            # If two labels point to the same start state don't duplicate the printed states
            # Skip all duplicate states except for the last
            duplicates = sm.get_duplicate_labels(label)
            if len(duplicates) > 1 and label != duplicates[-1]:
                self.unindent(None)
                continue

            for m in self.merge_states(states):
                self.output(self.merged_state_to_decohack(m))

            if goto is not None:
                if goto != 'continue':
                    self.output(goto)
            else:
                self.output('stop')

            self.unindent(None)

    def make_mobj_state_machine(self, mobj):
        # Collect the state labels this mobj has
        labels = {}
        for label in DecohackWriter.state_names:
            prop_name = '{}state'.format(label)
            state = mobj.props.get(prop_name)
            if state:
                labels[label] = state

        return StateMachine(self.info, labels)

    def output_mobj_states(self, mobj):
        self.output('states')
        self.indent('{')

        sm = self.make_mobj_state_machine(mobj)
        self.output_state_machine(sm)

        self.unindent('}')

    def output_mobj(self, mobj):
        self.output_spacer()

        header = 'thing {}'.format(mobj.name)
        if mobj.alias:
            header += ' "{}"'.format(mobj.alias)

        self.output(header)
        self.indent('{')

        self.output_mobj_props(mobj)
        self.output_mobj_sounds(mobj)
        self.output_mobj_flags(mobj)
        self.output_mobj_states(mobj)

        self.unindent('}')

    def make_weapon_state_machine(self, weapon):
        labels = {}
        for label in DecohackWriter.weapon_state_names:
            state = weapon.get(label)
            if state:
                labels[label] = state

        return StateMachine(self.info, labels)

    def output_weapon(self, weapon, name, index):
        self.output_spacer()

        self.output('weapon {} "{}"'.format(index, name))
        self.indent('{')

        sm = self.make_weapon_state_machine(weapon)
        self.output('states')
        self.indent('{')


        self.unindent('}')

        self.unindent('}')

    def output_weapon(self, index, weapon_name, weapon):
        self.output_spacer()

        self.output('weapon {} : "{}"'.format(index, weapon_name))
        self.indent('{')
        self.output('ammotype: {}'.format(weapon['ammotype']))
        self.unindent('}')
