import bpy
import arm.api
import arm.material.mat_state as mat_state
import arm.material.cycles as cycles
import arm.material.make_attrib as make_attrib
import arm.material.make_finalize as make_finalize
import arm.material.mat_utils as mat_utils
import arm.assets as assets
import arm.utils

def register():
    arm.api.add_driver('Celshade', draw_props, make_rpass, make_rpath)

def draw_props(layout):
    rpdat = arm.utils.get_rp()

def make_rpass(rpass):
    if rpass == 'mesh':
        return make_mesh_pass(rpass)
    return None

def make_mesh_pass(rpass):
    con = { 'name': rpass, 'depth_write': True, 'compare_mode': 'less', 'cull_mode': 'clockwise' }

    con_mesh = mat_state.data.add_context(con)
    mat_state.con_mesh = con_mesh

    wrd = bpy.data.worlds['Arm']
    vert = con_mesh.make_vert()
    frag = con_mesh.make_frag()
    geom = None
    tesc = None
    tese = None

    vert.add_uniform('mat3 N', '_normalMatrix')
    vert.write_attrib('vec4 spos = vec4(pos.xyz, 1.0);')
    frag.ins = vert.outs

    frag.add_include('compiled.glsl')
    frag.add_uniform('vec3 sunDir', '_sunDirection')
    frag.add_uniform('vec3 sunCol', '_sunColor')
    frag.add_uniform('float envmapStrength', link='_envmapStrength')
    frag.write('float visibility = 1.0;')
    frag.write('float dotNL = max(dot(n, sunDir), 0.0);')

    is_shadows = '_ShadowMap' in wrd.world_defs
    if is_shadows:
        vert.add_out('vec4 lightPos')
        vert.add_uniform('mat4 LWVP', '_biasLightWorldViewProjectionMatrix')
        vert.write('lightPos = LWVP * spos;')
        frag.add_include('std/shadows.glsl')
        frag.add_uniform('sampler2DShadow shadowMap')
        frag.add_uniform('float shadowsBias', '_sunShadowsBias')
        frag.write('if (lightPos.w > 0.0) {')
        frag.write('vec3 lPos = lightPos.xyz / lightPos.w;')
        frag.write('const vec2 smSize = shadowmapSize;')
        frag.write('visibility *= PCF(shadowMap, lPos.xy, lPos.z - shadowsBias, smSize);')
        frag.write('}')

    frag.write('vec3 basecol;')
    frag.write('float roughness;')
    frag.write('float metallic;')
    frag.write('float occlusion;')
    frag.write('float specular;')
    is_displacement = mat_utils.disp_linked(mat_state.output_node)
    arm_discard = mat_state.material.arm_discard
    if arm_discard:
        frag.write('float opacity;')
    cycles.parse(mat_state.nodes, con_mesh, vert, frag, geom, tesc, tese, parse_opacity=arm_discard, parse_displacement=is_displacement)

    if is_displacement:
        vert.add_uniform('mat4 W', link='_worldMatrix')
        vert.add_uniform('mat4 VP', link='_viewProjectionMatrix')
        vert.write('vec4 wpos = W * spos;')
        vert.write('wpos.xyz += wnormal * disp * 0.1;')
        vert.write('gl_Position = VP * wpos;')
    else:
        make_attrib.write_vertpos(vert)

    if arm_discard:
        opac = mat_state.material.arm_discard_opacity
        frag.write('if (opacity < {0}) discard;'.format(opac))

    if con_mesh.is_elem('tex'):
        vert.add_out('vec2 texCoord')
        vert.add_uniform('float texUnpack', link='_texUnpack')
        vert.write_attrib('texCoord = tex * texUnpack;')

    if con_mesh.is_elem('col'):
        vert.add_out('vec3 vcolor')
        vert.write_attrib('vcolor = col;')

    if con_mesh.is_elem('tang'):
        vert.add_out('mat3 TBN')
        make_attrib.write_norpos(con_mesh, vert, declare=True)
        vert.write('vec3 tangent = normalize(N * tang.xyz);')
        vert.write('vec3 bitangent = normalize(cross(wnormal, tangent));')
        vert.write('TBN = mat3(tangent, bitangent, wnormal);')
    else:
        vert.add_out('vec3 wnormal')
        make_attrib.write_norpos(con_mesh, vert)
        frag.write_attrib('vec3 n = normalize(wnormal);')

    frag.add_out('vec4 fragColor')
    frag.write('vec3 direct = basecol * step(0.5, dotNL) * visibility * sunCol;')
    frag.write('vec3 indirect = basecol * envmapStrength;')
    frag.write('fragColor = vec4(direct + indirect, 1.0);')

    if '_LDR' in wrd.world_defs:
        frag.write('fragColor.rgb = pow(fragColor.rgb, vec3(1.0 / 2.2));')

    assets.vs_equal(con_mesh, assets.shader_cons['mesh_vert'])

    make_finalize.make(con_mesh)

    return con_mesh

def make_rpath():
    assets_path = arm.utils.get_sdk_path() + 'armory/Assets/'
    wrd = bpy.data.worlds['Arm']
    rpdat = arm.utils.get_rp()

    if rpdat.rp_hdr:
        assets.add_khafile_def('rp_hdr')
    else:
        wrd.world_defs += '_LDR'

    if rpdat.rp_shadows:
        wrd.world_defs += '_ShadowMap'
        assets.add_khafile_def('rp_shadowmap')
        assets.add_khafile_def('rp_shadowmap_cascade={0}'.format(rpdat.rp_shadowmap_cascade))
        assets.add_khafile_def('rp_shadowmap_cube={0}'.format(rpdat.rp_shadowmap_cube))

    assets.add_khafile_def('rp_background={0}'.format(rpdat.rp_background))
    if rpdat.rp_background == 'World':
        assets.add_shader_pass('world_pass')
        if '_EnvClouds' in wrd.world_defs:
            assets.add(assets_path + 'noise256.png')
            assets.add_embedded_data('noise256.png')

    if rpdat.rp_render_to_texture:
        assets.add_khafile_def('rp_render_to_texture')

        if rpdat.rp_compositornodes:
            assets.add_khafile_def('rp_compositornodes')
            compo_depth = False
            if rpdat.arm_tonemap != 'Off':
                wrd.compo_defs = '_CTone' + rpdat.arm_tonemap
            if rpdat.rp_antialiasing == 'FXAA':
                wrd.compo_defs += '_CFXAA'
            if rpdat.arm_letterbox:
                wrd.compo_defs += '_CLetterbox'
            if rpdat.arm_grain:
                wrd.compo_defs += '_CGrain'
            if bpy.data.scenes[0].cycles.film_exposure != 1.0:
                wrd.compo_defs += '_CExposure'
            if rpdat.arm_fog:
                wrd.compo_defs += '_CFog'
                compo_depth = True
            if len(bpy.data.cameras) > 0 and bpy.data.cameras[0].dof.use_dof:
                wrd.compo_defs += '_CDOF'
                compo_depth = True
            if compo_depth:
                wrd.compo_defs += '_CDepth'
                assets.add_khafile_def('rp_compositordepth')
            if rpdat.arm_lens_texture != '':
                wrd.compo_defs += '_CLensTex'
                assets.add_embedded_data('lenstexture.jpg')
            if rpdat.arm_fisheye:
                wrd.compo_defs += '_CFishEye'
            if rpdat.arm_vignette:
                wrd.compo_defs += '_CVignette'
            if rpdat.arm_lensflare:
                wrd.compo_defs += '_CGlare'
            if rpdat.arm_lut_texture != '':
                wrd.compo_defs += '_CLUT'
                assets.add_embedded_data('luttexture.jpg')
            if '_CDOF' in wrd.compo_defs or '_CFXAA' in wrd.compo_defs or '_CSharpen' in wrd.compo_defs:
                wrd.compo_defs += '_CTexStep'
            if '_CDOF' in wrd.compo_defs or '_CFog' in wrd.compo_defs or '_CGlare' in wrd.compo_defs:
                wrd.compo_defs += '_CCameraProj'
            assets.add_shader_pass('compositor_pass')
        else:
            assets.add_shader_pass('copy_pass')

        assets.add_khafile_def('rp_antialiasing={0}'.format(rpdat.rp_antialiasing))

        if rpdat.rp_antialiasing == 'SMAA' or rpdat.rp_antialiasing == 'TAA':
            assets.add_shader_pass('smaa_edge_detect')
            assets.add_shader_pass('smaa_blend_weight')
            assets.add_shader_pass('smaa_neighborhood_blend')
            assets.add(assets_path + 'smaa_area.png')
            assets.add(assets_path + 'smaa_search.png')
            assets.add_embedded_data('smaa_area.png')
            assets.add_embedded_data('smaa_search.png')
            wrd.world_defs += '_SMAA'
            if rpdat.rp_antialiasing == 'TAA':
                assets.add_shader_pass('taa_pass')
                assets.add_shader_pass('copy_pass')

        if rpdat.rp_antialiasing == 'TAA' or rpdat.rp_motionblur == 'Object':
            assets.add_khafile_def('arm_veloc')
            wrd.world_defs += '_Veloc'
            if rpdat.rp_antialiasing == 'TAA':
                assets.add_khafile_def('arm_taa')

        assets.add_khafile_def('rp_supersampling={0}'.format(rpdat.rp_supersampling))
        if rpdat.rp_supersampling == '4':
            assets.add_shader_pass('supersample_resolve')

        if rpdat.rp_volumetriclight:
            wrd.world_defs += '_Sun'
            assets.add_khafile_def('rp_volumetriclight')
            assets.add_shader_pass('volumetric_light')
            assets.add_shader_pass('blur_bilat_pass')
            assets.add_shader_pass('blur_bilat_blend_pass')
            assets.add(assets_path + 'blue_noise64.png')
            assets.add_embedded_data('blue_noise64.png')

        if rpdat.rp_bloom:
            assets.add_khafile_def('rp_bloom')
            assets.add_shader_pass('bloom_pass')
            assets.add_shader_pass('blur_gaus_pass')

        if rpdat.arm_rp_resolution == 'Custom':
            assets.add_khafile_def('rp_resolution_filter={0}'.format(rpdat.arm_rp_resolution_filter))
