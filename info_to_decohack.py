#
# Script to dump Doom's info.c out as Decohack
#
#   python3 info_to_decohack.py <path_to_info> [mobj name]
#
# Run with no mobj name to dump all mobjs
#

from collections import namedtuple
import sys
import re

State = namedtuple('State', 'sprite frame tics action nextstate misc1 misc2')
Property = namedtuple('Property', 'name value')
MobjInfo = namedtuple('MobjInfo', 'name props')

state_names = [
    'spawn',
    'see',
    'run',

    'meele',
    'missile',
    'refire',

    'crash',	# Heretic

    'pain',
    'death',
    'xdeath',

    'raise',
    ]

def parse_state_line(line):
    exp  = r'\s*\{([A-Z]{3}_[A-Z0-9]{4}),\s*'	# Sprite
    exp += r'([-0-9]+),\s*'			# Frame
    exp += r'([-0-9]+),\s*'			# Tics
    exp += r'\{?([A-Za-z0-9_]+)\}?,\s*'		# Action
    exp += r'([A-Za-z0-9_]+),\s*'		# Next state
    exp += r'([0-9]+),\s*'			# Misc 1
    exp += r'([0-9]+)\s*\},?\s*'		# Misc 2
    exp += r'// (.*)$'				# Comment

    m = re.match(exp, line)
    if m:
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

        return (name, State(sprite, frame, tics, action, nextstate, misc1, misc2))

    print('Bad state:')
    print(line)
    raise Exception('Bad state')

def parse_states(lines):
    states = {}
    done = False

    for i, line in enumerate(lines):
        if done:
            break

        if re.search(r'^state_t\s+states', line):
            for state_line in lines[i + 1:]:
                if state_line.startswith('};'):
                    done = True
                    break

                name, state = parse_state_line(state_line)
                states[name] = state

    return states

def parse_mobjinfo_property(line):
    tokens = line.split('//')
    if len(tokens) != 2:
        return None

    prop_name  = tokens[1].strip()
    prop_value = tokens[0].strip()
    if prop_value.endswith(','):
        prop_value = prop_value[:-1]
        if prop_value == 'S_NULL':
            prop_value = None

    return Property(prop_name, prop_value)

def parse_mobjinfo(lines):
    found_start = False
    mobj = None
    mobjs = {}

    for line in lines:
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
                mobjs[mobj.name] = mobj
                mobj = None

            else:
                prop = parse_mobjinfo_property(line)
                if prop:
                    mobj.props[prop.name] = prop.value

    return mobjs

def state_to_decohack(state):
    return merged_state_to_decohack([state])

def merged_state_to_decohack(merged):
    state = merged[0]
    string = ''

    string += '{} '.format(state.sprite[4:])

    for m in merged:
        string += '{}'.format(chr(ord('A') + (m.frame & 0x7fff)))

    if state.frame & 0x8000:
        string += '+'

    string += ' {}'.format(state.tics)

    if state.action:
        string += ' {}'.format(state.action)

    return string

def states_are_mergable(state_a, state_b):
    if state_a.sprite != state_b.sprite:
        return False

    if (state_a.frame & 0x8000) != (state_b.frame & 0x8000):
        return False

    if state_a.tics != state_b.tics:
        return False

    if state_a.action != state_b.action:
        return False

    return True

def merge_states(states):
    prev_state = None
    new_states = []
    merged = []

    for state in states:
        if not prev_state or not states_are_mergable(state, prev_state):
            if len(merged) > 0:
                new_states.append(merged)

            merged = []

        merged.append(state)
        prev_state = state

    if len(merged) > 0:
        new_states.append(merged)

    return new_states

def get_first_state(mobj, state_name):
    prop_name = '{}state'.format(state_name)
    if prop_name in mobj.props:
        try:
            return states[mobj.props[prop_name]]
        except:
            pass

    return None

def build_state_machine(mobj, state_name, states):
    goto = None

    items = []

    state = get_first_state(mobj, state_name)
    while state is not None:
        items.append(state)
        try:
            next_state = states[state.nextstate]
        except:
            next_state = None

        # Has this state looped/jumped to the start of another state
        if next_state is not None:
            for other_state_name in state_names:
                if next_state == get_first_state(mobj, other_state_name):
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

def mobj_props(mobj):
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

    props = []
    for name in prop_names:
        try:
            v = mobj.props[name]
            v = re.sub(r'\s*\*\s*FRACUNIT$', '', v)
            props.append((name, v))
        except:
            pass

    return props

def mobj_sounds(mobj):
    sound_names = [
        'seesound',
        'attacksound',
        'painsound',
        'deathsound',
        'activesound',
        ]

    props = []
    for sound in sound_names:
        try:
            v = mobj.props[sound]
            if v != 'sfx_None' and v != '0':
                v = re.sub(r'^sfx_', '', v)
                props.append((sound, '"{}"'.format(v)))
        except:
            pass

    return props

def mobj_flags(mobj):
    flags = []
    try:
        flags = mobj.props['flags'].split('|')
        flags = [f.strip() for f in flags]
        if '0' in flags:
            flags.remove('0')
    except:
        pass

    return flags

def mobj_to_decohack(mobj, states):
    lines = []

    print('thing {}'.format(mobj.name))
    print('{')

    # Properties
    nl = False
    for k, v in mobj_props(mobj):
        print('\t{}{}{}'.format(k, '\t' if len(k) >= 8 else '\t\t', v))
        nl = True
    if nl:
        print('')

    # Sounds
    nl = False
    for k, v in mobj_sounds(mobj):
        print('\t{}\t{}'.format(k, v))
        nl = True
    if nl:
        print('')

    # Flags
    nl = False
    print('\tclear flags')
    for flag in mobj_flags(mobj):
        print('\t+{}'.format(flag))
        nl = True
    if nl:
        print('')

    # States
    print('\tstates')
    print('\t{')

    for state_name in state_names:
        state_steps = []
        state_loop  = False

        items, goto = build_state_machine(mobj, state_name, states)
        if len(items) == 0:
            continue

        prev_item = None

        print('\t\t{}:'.format(state_name))

        for m in merge_states(items):
            print('\t\t\t{}'.format(merged_state_to_decohack(m)))

        if goto is not None:
            if goto == state_name:
                if state_name == 'refire' or state_name == 'run':
                    print('\t\t\tgoto {}'.format(goto))
                else:
                    print('\t\t\tloop')
            elif goto == 'continue':
                pass
            else:
                print('\t\t\tgoto {}'.format(goto))
        else:
            print('\t\t\tstop')


    print('\t}')
    print('}')

if __name__ == '__main__':

    lines = open(sys.argv[1], 'r').readlines()

    states = parse_states(lines)
    mobjs  = parse_mobjinfo(lines)

    if len(sys.argv) > 2:
        mobj = mobjs[sys.argv[2]]
        mobj_to_decohack(mobj, states)
    else:
        for mobj in mobjs.values():
            mobj_to_decohack(mobj, states)
            print('')
