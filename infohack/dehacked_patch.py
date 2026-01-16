class DehackedPatch:
    DEH_INT    = 'deh_int'
    DEH_FIXED  = 'deh_fixed'
    DEH_STRING = 'deh_string'

    def __init__(self, info):
        self.info = info

        self.things = {}
        self.frames = {}
        self.codeptrs = {}

    def log_patch(self, obj, obj_name, obj_prop, old_value, new_value):
        print('Patched {} {}.{}: {} -> {}'.format(obj, obj_name, obj_prop, old_value, new_value))

    def fixed_to_int(self, fixed):
        return int(fixed) >> 16

    def dehacked_frame_num_to_state(self, deh_frame_num):
        if deh_frame_num >= len(self.info.states):
            # TODO: extended states
            return None

        return self.info.states[deh_frame_num]

    def patch_things(self):
        prop_dict = {
            'Hit points'     : ('health',     DehackedPatch.DEH_INT),
            'Missile damage' : ('damage',     DehackedPatch.DEH_INT),
            'Pain chance'    : ('painchance', DehackedPatch.DEH_INT),
            'Speed'          : ('speed',      DehackedPatch.DEH_INT),
            'Width'          : ('radius',     DehackedPatch.DEH_FIXED),
            'Height'         : ('height',     DehackedPatch.DEH_FIXED),
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
            if deh_thing_num >= len(self.info.mobjs):
                # TODO: handle extended things
                continue

            thing = self.info.mobjs[deh_thing_num - 1]

            # Patch properties
            for deh_prop_name, (prop_name, deh_prop_type) in prop_dict.items():
                prop_value = deh_thing.get(deh_prop_name)
                if prop_value:
                    # Convert the value to the correct type if needed
                    if deh_prop_type == DehackedPatch.DEH_FIXED:
                        prop_value = self.fixed_to_int(prop_value)

                    self.log_patch('thing', thing.name, prop_name, thing.props[prop_name], prop_value)

                    thing.props[prop_name] = prop_value
                    thing.modified = True

            # Dechacked stores states as an index.
            # Convert to an entry in the info.states array
            for deh_state_name, state_name in state_dict.items():
                deh_state_index = deh_thing.get(deh_state_name)
                if deh_state_index:
                    try:
                        old_state_name = thing.props[state_name]
                    except:
                        old_state_name = 'None'

                    new_state_name = self.info.states[int(deh_state_index)].name
                    self.log_patch('thing', thing.name, state_name, old_state_name, new_state_name)

                    thing.props[state_name] = new_state_name
                    thing.modified = True

    def patch_frames(self):
        # TODO: mark state/things as modified
        #       need to find all things which use this state

        for deh_frame_num, deh_frame in self.frames.items():
            state = self.dehacked_frame_num_to_state(deh_frame_num)
            if state is None:
                continue

            sprite_index = deh_frame.get('Sprite number')
            if sprite_index:
                sprite_name = self.info.constants.sprite_names[int(sprite_index)]
                state.sprite = 'SPR_{}'.format(sprite_name)

            frame_index = deh_frame.get('Sprite subnumber')
            if frame_index:
                state.frame = int(frame_index)

            nextframe_index = deh_frame.get('Next frame')
            if nextframe_index:
                nextframe_index = int(nextframe_index)
                if nextframe_index >= len(self.info.states):
                    # TODO: handle extended states
                    continue

                new_nextstate_name = self.info.states[int(nextframe_index)].name

                self.log_patch('state', state.name, 'nextstate', state.nextstate, new_nextstate_name)

                state.nextstate = new_nextstate_name

            tics = deh_frame.get('Duration')
            if tics:
                state.tics = int(tics)

    def patch_codeptrs(self):
        for deh_frame_num, deh_codeptr in self.codeptrs.items():
            state = self.dehacked_frame_num_to_state(deh_frame_num)
            if state is None:
                continue

            self.log_patch('state', state.name, 'action', state.action, deh_codeptr)
            if deh_codeptr:
                state.action = 'A_{}'.format(deh_codeptr)
            else:
                state.action = None

    def patch(self):
        self.patch_things()
        self.patch_frames()
        self.patch_codeptrs()
