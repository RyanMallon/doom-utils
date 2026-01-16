from dataclasses import dataclass
from collections import namedtuple
import sys
import re

@dataclass
class State:
    sprite:	str
    frame:	str
    tics:	int
    action:	str
    nextstate:	str
    misc1:	int
    misc2:	int
    name:	str

@dataclass
class MobjInfo:
    name:	str
    props:	dict
    modified:	bool

# State = namedtuple('State', 'sprite frame tics action nextstate misc1 misc2 name')
#Property = namedtuple('Property', 'name value')
#MobjInfo = namedtuple('MobjInfo', 'name props modified')

class Info:
    def __init__(self, constants):
        self.constants = constants

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
