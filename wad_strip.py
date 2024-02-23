#
# Script to remove unused textures, patches and flats from a wad.
# Run with:
#
#   python3 wad_strip.py <iwad.wad> <pwad.wad> <output.wad>
#
from collections import namedtuple
import struct
import sys

Lump = namedtuple('Lump', 'name offset size')
Texture = namedtuple('Texture', 'name masked width height columndir patches')
MapPatch = namedtuple('MapPatch', 'name x y stepdir colormap')

def sanitize_lump_name(name):
    return name.decode('utf8').rstrip('\x00').upper()

class Wad(object):
    def __init__(self, filename):
        self.fd = open(filename, 'rb')
        self.lumps = self.parse_lump_table()

        self.patches = self.load_patches()
        self.textures = self.load_textures()
        self.flats = self.load_flats()

    def parse_lump_table(self):
        self.fd.seek(0)
        header = self.fd.read(12)
        wad_type, num_lumps, table_offset = struct.unpack('<4sII', header)

        lumps = []
        self.fd.seek(table_offset)
        for lump_index in range(num_lumps):
            lump_header = self.fd.read(16)
            lump_offset, lump_size, lump_name = struct.unpack('<II8s', lump_header)
            lumps.append(Lump(sanitize_lump_name(lump_name), lump_offset, lump_size))

        return lumps

    def get_lump(self, lump_name):
        for lump in self.lumps:
            if lump.name == lump_name:
                return lump

        return None

    def get_all_lumps(self, lump_name):
        lumps = []
        for lump in self.lumps:
            if lump.name == lump_name:
                lumps.append(lump)

        return lumps

    def read_lump_data(self, lump):
        self.fd.seek(lump.offset)
        return self.fd.read(lump.size)

    def read_lump(self, lump_name):
        lump = self.get_lump(lump_name)
        if not lump:
            return None

        return self.read_lump_data(lump)

    def load_textures(self):
        return self.load_texture_lump('TEXTURE1')

    def load_texture_lump(self, lump_name):
        print('Loading textures')

        lump = self.read_lump(lump_name)
        textures = []

        texture_offsets = []
        num_textures = struct.unpack('<I', lump[0:4])[0]

        offset = 4
        for i in range(num_textures):
            texture_offset = struct.unpack('<I', lump[offset:offset + 4])[0]
            texture_offsets.append(texture_offset)
            offset += 4

        for i in range(num_textures):
            offset = texture_offsets[i]
            name, masked, width, height, columndir, num_patches = struct.unpack('<8sIHHIH', lump[offset:offset + 22])
            offset += 22

            map_patches = []
            for j in range(num_patches):
                x, y, patch_index, stepdir, colormap = struct.unpack('<HHHHH', lump[offset :offset + 10])
                map_patches.append(MapPatch(self.patches[patch_index], x, y, stepdir, colormap))
                offset += 10

            textures.append(Texture(sanitize_lump_name(name), masked, width, height, columndir, map_patches))

        return textures

    def load_patches(self):
        print('Loading patches')

        lump = self.read_lump('PNAMES')
        patches = []

        num_patches = struct.unpack('<I', lump[0:4])[0]

        offset = 4
        for i in range(num_patches):
            name = struct.unpack('<8s', lump[offset:offset + 8])[0]
            patches.append(sanitize_lump_name(name))
            offset += 8

        return patches

    def load_flats(self):
        print('Loading flats')

        flats = []
        for lump in self.lumps_between_markers('F_START', 'F_END'):
            flats.append(lump.name)

        return flats

    def load_animated_lump(self, flats, textures):
        print('Loading animated lump')

        lump = self.read_lump('ANIMATED')
        if not lump:
            return ([], [])

        anim_flats = []
        anim_textures = []

        for offset in range(0, len(lump), 23):
            if len(lump) - offset < 23:
                break

            kind, name_last, name_first, _ = struct.unpack('<B9s9sI', lump[offset:offset + 23])
            if kind == 0xff:
                break

            name_first = sanitize_lump_name(name_first)
            name_last = sanitize_lump_name(name_last)

            if kind == 0:
                do_append = False
                lump_names = []
                for flat in flats:
                    if flat == name_first:
                        do_append = True
                    if do_append:
                        lump_names.append(flat)
                    if flat == name_last:
                        break

                anim_flats.append(lump_names)

            elif kind == 1:
                do_append = False
                lump_names = []
                for texture in textures:
                    if texture.name == name_first:
                        do_append = True
                    if do_append:
                        lump_names.append(texture.name)
                    if texture.name == name_last:
                        break

                anim_textures.append(lump_names)

        return (anim_flats, anim_textures)

    def load_switches_lump(self):
        print('Loading switches lump')

        lump = self.read_lump('SWITCHES')
        if not lump:
            return []

        anim_textures = []

        for offset in range(0, len(lump), 20):
            name_off, name_on, kind = struct.unpack('<9s9sH', lump[offset:offset + 20])
            if kind == 0x00:
                break

            anim_textures.append([sanitize_lump_name(name_off), sanitize_lump_name(name_on)])

        return anim_textures

    def load_animations(self, flats, textures):
        print('Loading animations')

        anim_flats, anim_textures = self.load_animated_lump(flats, textures)

        #
        # Switches can be animated. In this case the base on/off textures are
        # in the SWITCHES lump, and the animation frames are in the ANIMATED
        # lump. Extend the list of textures for switches to include any
        # additional animation frames.
        #
        switches = []
        switch_anim_base = self.load_switches_lump()

        print('Finding animated switch textures')
        for texture_on, texture_off in switch_anim_base:
            switch_anim = [texture_off, texture_on]
            for animation in anim_textures:
                if texture_on in animation or texture_off in animation:
                    switch_anim.extend(animation)

            switches.append(switch_anim)

        anim_textures.extend(switch_anim)

        return (anim_flats, anim_textures)

    def lumps_between_markers(self, marker_start, marker_end):
        in_range = False
        lumps = []

        for lump in self.lumps:
            if in_range:
                if lump.name == marker_end:
                    break

                lumps.append(lump)

            elif lump.name == marker_start:
                in_range = True

        return lumps

    def texture_add(self, textures, name):
        name = sanitize_lump_name(name)
        if name != '-':
            textures.add(name)

    def find_used_textures(self):
        print('Finding used textures')

        textures = set()

        for lump in self.get_all_lumps('SIDEDEFS'):
            lump = self.read_lump_data(lump)
            for offset in range(0, len(lump), 30):
                _, _, tex_upper, tex_mid, tex_lower, _ = struct.unpack('<HH8s8s8sH', lump[offset:offset + 30])
                self.texture_add(textures, tex_upper)
                self.texture_add(textures, tex_mid)
                self.texture_add(textures, tex_lower)

        # Sky textures are special
        textures.update(['SKY1', 'SKY2', 'SKY3'])

        return list(textures)

    def find_used_flats(self):
        flats = set()
        for lump in self.get_all_lumps('SECTORS'):
            lump = self.read_lump_data(lump)
            for offset in range(0, len(lump), 26):
                _, _, flat_floor, flat_ceiling, _, _, _ = struct.unpack('<HH8s8sHHH', lump[offset:offset + 26])
                flats.add(sanitize_lump_name(flat_floor))
                flats.add(sanitize_lump_name(flat_ceiling))

        return list(flats)

class UsedTextureSet(object):
    def __init__(self, iwad, pwad):
        self.pwad = pwad

        self.textures = iwad.textures + pwad.textures
        self.patches = iwad.patches + pwad.patches
        self.flats = iwad.flats + pwad.flats

        self.used_textures = iwad.find_used_textures() + pwad.find_used_textures()

        anim_flats, anim_textures = pwad.load_animations(self.flats, self.textures)
        self.used_textures = self.mark_used_animations(self.used_textures, anim_textures)

        self.used_patches = self.find_used_patches()

        self.used_flats = iwad.find_used_flats() + pwad.find_used_flats()
        self.used_flats = self.mark_used_animations(self.used_flats, anim_flats)

    def find_used_patches(self):
        print('Finding used patches')

        patches = set()

        for texture_name in self.used_textures:
            for texture in self.textures:
                if texture.name == texture_name:
                    for map_patch in texture.patches:
                        patches.add(map_patch.name)
                    break

        return list(patches)

    def mark_used_animations(self, textures, animations):
        print('Marking used animations')

        new_textures = set(textures)

        for texture in textures:
            for animation in animations:
                if texture in animation:
                    new_textures.update(animation)

        return list(new_textures)

    def get_texture(self, name):
        for texture in self.textures:
            if texture.name == name:
                return texture

        return None

    def get_used_patch_index(self, name):
        for i, patch in enumerate(self.used_patches):
            if patch == name:
                return i

        return -1

    def removable_lumps(self):
        unused_patches = []
        for patch in self.patches:
            if patch not in self.used_patches and patch not in self.used_flats:
                unused_patches.append(patch)

        unused_flats = []
        for flat in self.flats:
            if flat not in self.used_flats and flat not in self.used_patches:
                unused_flats.append(flat)

        return unused_patches + unused_flats

    def build_pnames_lump(self):
        lump = struct.pack('<I', len(self.used_patches))
        for patch in self.used_patches:
            lump += struct.pack('<8s', patch.encode())

        return lump

    def build_textures_lump(self):
        print('Building textures lump')

        #
        # Python sets (used to build self.used_textures) are unordered.
        # Write the new texture lump with the same ordering as the original,
        # just with unused textures removed. Animated textures will break
        # if their ordering is incorrect.
        #
        used_textures = []
        for texture in self.textures:
            if texture.name in self.used_textures:
                used_textures.append(texture.name)

        lump = struct.pack('<I', len(used_textures))

        offset_table = []
        offset = 4 + (4 * len(used_textures))

        data = b''
        for texture_name in used_textures:
            offset_table.append(offset)

            texture = self.get_texture(texture_name)
            data += struct.pack('<8sIHHIH', texture.name.encode(), texture.masked, texture.width, texture.height, texture.columndir, len(texture.patches))

            for map_patch in texture.patches:
                patch_index = self.get_used_patch_index(map_patch.name)
                data += struct.pack('<HHHHH', map_patch.x, map_patch.y, patch_index, map_patch.stepdir, map_patch.colormap)

            offset += 22 + (10 * len(texture.patches))

        for offset in offset_table:
            lump += struct.pack('<I', offset)

        lump += data
        return lump

    def build_animated_lump(self):
        print('Building animated lump')

        orig_lump = self.pwad.read_lump('ANIMATED')

        lump = b''
        for offset in range(0, len(orig_lump), 23):
            if len(orig_lump) - offset < 23:
                break

            entry = orig_lump[offset:offset + 23]
            kind, _, name_first, _ = struct.unpack('<B9s9sI', entry)
            name_first = sanitize_lump_name(name_first)

            if kind == 0 and name_first not in self.used_flats:
                continue
            elif kind == 1 and name_first not in self.used_textures:
                continue

            lump += entry

        return lump + b'\xff'

    def build_switches_lump(self):
        print('Building switches lump')

        orig_lump = self.pwad.read_lump('SWITCHES')

        lump = b''
        for offset in range(0, len(orig_lump), 20):
            entry = orig_lump[offset:offset + 20]
            name_off, name_on, kind = struct.unpack('<9s9sH', entry)
            if kind == 0x00:
                break

            if sanitize_lump_name(name_on) not in self.used_textures:
                continue

            lump += entry

        return lump + (b'\x00' * 20)

class WadWriter(object):
    def __init__(self, pwad, used):
        self.pwad = pwad
        self.used = used

    def write(self, filename):
        fd = open(filename, 'wb')

        removable = self.used.removable_lumps()

        lumps = []
        for lump in pwad.lumps:
            if lump.name.startswith('_') or lump.name.startswith('\\'):
                continue
            if lump.name in removable:
                continue

            lumps.append(lump)

        fd.write(struct.pack('<4sII', b'PWAD', len(lumps), 12))

        lump_blobs = []
        for lump in lumps:
            if lump.name == 'PNAMES':
                blob = self.used.build_pnames_lump()
            elif lump.name == 'TEXTURE1':
                blob = self.used.build_textures_lump()
            elif lump.name == 'ANIMATED':
                blob = self.used.build_animated_lump()
            elif lump.name == 'SWITCHES':
                blob = self.used.build_switches_lump()
            else:
                blob = pwad.read_lump_data(lump)

            lump_blobs.append((lump.name, blob))

        offset = 12 + (16 * len(lump_blobs))
        for lump_name, lump_data in lump_blobs:
            fd.write(struct.pack('<II8s', offset, len(lump_data), lump_name.encode()))
            offset += len(lump_data)

        for _, lump_data in lump_blobs:
            fd.write(lump_data)

        fd.close()

if __name__ == '__main__':
    iwad = Wad(sys.argv[1])
    pwad = Wad(sys.argv[2])
    outfile = sys.argv[3]

    writer = WadWriter(pwad, UsedTextureSet(iwad, pwad))
    writer.write(outfile)
