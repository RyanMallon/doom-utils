class DehackedPatch:
    DEH_INT    = 'deh_int'
    DEH_FIXED  = 'deh_fixed'
    DEH_STRING = 'deh_string'

    def __init__(self, info, args):
        self.info = info
        self.args = args

        self.things = {}
        self.frames = {}
        self.pointers = []
        self.codeptrs = {}

    def log_patch(self, obj, obj_name, obj_prop, old_value, new_value):
        if self.args.debug_deh_patch:
            print('Patched {} {}.{}: {} -> {}'.format(obj, obj_name, obj_prop, old_value, new_value))

    def log_patch_thing(self, thing, prop_name, old_value, new_value):
        if self.args.debug_deh_patch:
            print('Patched thing [{:4d}] {}.{}: {} -> {}'.format(self.info.mobjs.index(thing) + 1,
                                                                 thing.name, prop_name,
                                                                 old_value, new_value))

    def log_patch_state(self, state, prop_name, old_value, new_value):
        if self.args.debug_deh_patch:
            print('Patched state [{:4d}] {}.{}: {} -> {}'.format(self.info.states.index(state),
                                                                 state.name, prop_name,
                                                                 old_value, new_value))


    def fixed_to_int(self, fixed):
        return int(fixed) >> 16

    def dehacked_frame_num_to_state(self, deh_frame_num):
        if deh_frame_num >= len(self.info.states):
            # TODO: extended states
            return None

        return self.info.states[deh_frame_num]

    def patch_thing_props(self, deh_thing, thing):
        prop_dict = {
            'Hit points'     : ('health',     DehackedPatch.DEH_INT),
            'Missile damage' : ('damage',     DehackedPatch.DEH_INT),
            'Pain chance'    : ('painchance', DehackedPatch.DEH_INT),
            'Speed'          : ('speed',      DehackedPatch.DEH_INT),
            'Width'          : ('radius',     DehackedPatch.DEH_FIXED),
            'Height'         : ('height',     DehackedPatch.DEH_FIXED),
        }

        for deh_prop_name, (prop_name, deh_prop_type) in prop_dict.items():
            prop_value = deh_thing.get(deh_prop_name)
            if prop_value:
                # Convert the value to the correct type if needed
                if deh_prop_type == DehackedPatch.DEH_FIXED:
                    prop_value = self.fixed_to_int(prop_value)

                self.log_patch_thing(thing, prop_name, thing.props[prop_name], prop_value)

                thing.props[prop_name] = prop_value
                thing.modified = True

    def patch_thing_sounds(self, deh_thing, thing):
        sound_dict = {
            'Action sound'   : 'activesound',
            'Alert sound'    : 'seesound',
            'Attack sound'   : 'attacksound',
            'Pain sound'     : 'painsound',
            'Death sound'    : 'deathsound',
        }

        for deh_sound_prop, sound_prop in sound_dict.items():
            sound_index = deh_thing.get(deh_sound_prop)
            if sound_index:
                # TODO: handle extended sounds
                sound_name = self.info.constants.sound_names[int(sound_index)]

                self.log_patch_thing(thing, sound_prop, thing.props[sound_prop], sound_name)
                thing.props[sound_prop] = sound_name
                thing.modified = True

    def patch_thing_flags_int(self, deh_thing, thing, flag_bits):
        flags = []
        for i in range(0, 31):
            flag_val = (1 << i)
            if flag_bits & flag_val:
                flag_name = self.info.constants.mobj_flags.get(flag_val)
                if not flag_name:
                    print('Unknown flag {:x} for thing {}'.format(flag_val, thing.name))
                else:
                    flags.append(flag_name)

        if len(flags) == 0:
            return None
        return '|'.join(flags)

    def patch_thing_flags(self, deh_thing, thing):
        flag_bits = deh_thing.get('Bits')

        if flag_bits:
            # Flags can either be an integer or string mneumonics
            try:
                new_flags = self.patch_thing_flags_int(deh_thing, thing, int(flag_bits))
            except:
                new_flags = flag_bits.replace('+', '|')

            self.log_patch_thing(thing, 'flags', thing.props['flags'], new_flags)
            thing.props['flags'] = new_flags
            thing.modified = True

    def patch_thing_states(self, deh_thing, thing):
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
                self.log_patch_thing(thing, state_name, old_state_name, new_state_name)

                thing.props[state_name] = new_state_name
                thing.modified = True

    def patch_things(self):
        for deh_thing_num, deh_thing in self.things.items():
            if deh_thing_num >= len(self.info.mobjs):
                # TODO: handle extended things
                continue

            thing = self.info.mobjs[deh_thing_num - 1]

            # Dehacked can give friendly names to things
            alias = deh_thing['alias']
            if alias:
                thing.alias = alias

            self.patch_thing_props(deh_thing, thing)
            self.patch_thing_sounds(deh_thing, thing)
            self.patch_thing_flags(deh_thing, thing)
            self.patch_thing_states(deh_thing, thing)

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

                self.log_patch_state(state, 'nextstate', state.nextstate, new_nextstate_name)

                state.nextstate = new_nextstate_name

            tics = deh_frame.get('Duration')
            if tics:
                state.tics = int(tics)

    def patch_pointers(self):
        # Old style code pointers
        actions = []

        # Build a list first since source actions may get overwritten
        for src_frame_index, dst_frame_index in self.pointers:
            src_state = self.dehacked_frame_num_to_state(src_frame_index)
            dst_state = self.dehacked_frame_num_to_state(dst_frame_index)
            actions.append((dst_state, src_state.action))

        # Apply them
        for state, action in actions:
            self.log_patch_state(state, 'action', state.action, action)
            state.action = action

    def patch_codeptrs(self):
        for deh_frame_num, deh_codeptr in self.codeptrs.items():
            state = self.dehacked_frame_num_to_state(deh_frame_num)
            if state is None:
                continue

            self.log_patch_state(state, 'action', state.action, deh_codeptr)
            if deh_codeptr:
                state.action = 'A_{}'.format(deh_codeptr)
            else:
                state.action = None

    def patch(self):
        self.patch_things()
        self.patch_frames()
        self.patch_pointers()
        self.patch_codeptrs()
