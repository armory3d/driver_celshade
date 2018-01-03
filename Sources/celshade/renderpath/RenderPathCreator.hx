package celshade.renderpath;

import iron.RenderPath;

class RenderPathCreator {

	static var path:RenderPath;

	public static function get():RenderPath {
		path = new RenderPath();
		init();
		path.commands = commands;
		return path;
	}

	static function init() {

		#if kha_webgl
		initEmpty();
		#end

		#if (rp_background == "World")
		{
			path.loadShader("shader_datas/world_pass/world_pass");
		}
		#end

		#if rp_render_to_texture
		{
			path.createDepthBuffer("main", "DEPTH24");

			var t = new RenderTargetRaw();
			t.name = "lbuf";
			t.width = 0;
			t.height = 0;
			t.format = getHdrFormat();
			t.displayp = getDisplayp();
			var ss = getSuperSampling();
			if (ss != 1) t.scale = ss;
			t.depth_buffer = "main";
			path.createRenderTarget(t);

			#if rp_compositornodes
			{
				path.loadShader("shader_datas/compositor_pass/compositor_pass");
			}
			#else
			{
				path.loadShader("shader_datas/copy_pass/copy_pass");
			}
			#end
		}
		#end
	}

	static function commands() {

		#if rp_shadowmap
		{
			var faces = path.getLamp(path.currentLampIndex).data.raw.shadowmap_cube ? 6 : 1;
			for (i in 0...faces) {
				if (faces > 1) path.currentFace = i;
				path.setTarget(getShadowMap());
				path.clearTarget(null, 1.0);
				path.drawMeshes("shadowmap");
			}
			path.currentFace = -1;
		}
		#end

		#if rp_render_to_texture
		{
			path.setTarget("lbuf");
		}
		#else
		{
			path.setTarget("");
		}
		#end

		#if (rp_background == "Clear")
		{
			path.clearTarget(-1, 1.0);
		}
		#else
		{
			path.clearTarget(null, 1.0);
		}
		#end

		#if rp_shadowmap
		{
			bindShadowMap();
		}
		#end

		path.drawMeshes("mesh");
		#if (rp_background == "World")
		{
			path.drawSkydome("shader_datas/world_pass/world_pass");
		}
		#end

		#if rp_render_to_texture
		{
			path.setTarget("");
			path.bindTarget("lbuf", "tex");

			#if rp_compositornodes
			{
				path.drawShader("shader_datas/compositor_pass/compositor_pass");
			}
			#else
			{
				path.drawShader("shader_datas/copy_pass/copy_pass");
			}
			#end
		}
		#end
	}

	static inline function getSuperSampling():Int {
		#if (rp_supersampling == 2)
		return 2;
		#elseif (rp_supersampling == 4)
		return 4;
		#else
		return 1;
		#end
	}

	static inline function getHdrFormat():String {
		#if rp_hdr
		return "RGBA64";
		#else
		return "RGBA32";
		#end
	}

	static inline function getDisplayp():Null<Int> {
		#if (rp_resolution == 480)
		return 480;
		#elseif (rp_resolution == 720)
		return 720;
		#elseif (rp_resolution == 1080)
		return 1080;
		#elseif (rp_resolution == 1440)
		return 1440;
		#elseif (rp_resolution == 2160)
		return 2160;
		#else
		return null;
		#end
	}

	static function bindShadowMap() {
		var target = shadowMapName();
		if (target == "shadowMapCube") {
			#if kha_webgl
			// Bind empty map to non-cubemap sampler to keep webgl happy
			path.bindTarget("arm_empty", "shadowMap");
			#end
			path.bindTarget("shadowMapCube", "shadowMapCube");
		}
		else {
			#if kha_webgl
			// Bind empty map to cubemap sampler
			path.bindTarget("arm_empty_cube", "shadowMapCube");
			#end
			path.bindTarget("shadowMap", "shadowMap");
		}
	}

	static function shadowMapName():String {
		return path.getLamp(path.currentLampIndex).data.raw.shadowmap_cube ? "shadowMapCube" : "shadowMap";
	}

	static function getShadowMap():String {
		var target = shadowMapName();
		var rt = path.renderTargets.get(target);
		// Create shadowmap on the fly
		if (rt == null) {
			if (path.getLamp(path.currentLampIndex).data.raw.shadowmap_cube) {
				// Cubemap size
				var size = Std.int(path.getLamp(path.currentLampIndex).data.raw.shadowmap_size);
				var t = new RenderTargetRaw();
				t.name = target;
				t.width = size;
				t.height = size;
				t.format = "DEPTH16";
				t.is_cubemap = true;
				rt = path.createRenderTarget(t);
			}
			else { // Non-cube sm
				var sizew = path.getLamp(path.currentLampIndex).data.raw.shadowmap_size;
				var sizeh = sizew;
				#if arm_csm // Cascades - atlas on x axis
				sizew = sizeh * iron.object.LampObject.cascadeCount;
				#end
				var t = new RenderTargetRaw();
				t.name = target;
				t.width = sizew;
				t.height = sizeh;
				t.format = "DEPTH16";
				rt = path.createRenderTarget(t);
			}
		}
		return target;
	}

	#if kha_webgl
	static function initEmpty() {
		// Bind empty when requested target is not found
		var tempty = new RenderTargetRaw();
		tempty.name = "arm_empty";
		tempty.width = 1;
		tempty.height = 1;
		tempty.format = "DEPTH16";
		path.createRenderTarget(tempty);
		var temptyCube = new RenderTargetRaw();
		temptyCube.name = "arm_empty_cube";
		temptyCube.width = 1;
		temptyCube.height = 1;
		temptyCube.format = "DEPTH16";
		temptyCube.is_cubemap = true;
		path.createRenderTarget(temptyCube);
	}
	#end
}
