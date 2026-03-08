/**
 * planet_globe.js — VGA-era spinning globe for the universe browser baseball card.
 *
 * Procedurally raycasts a Lambertian-shaded sphere. Palettes are driven by
 * planet_type_code / moon_type_code / star_type from the API response.
 * Renders to a <canvas> element; animation via requestAnimationFrame.
 */
(function () {
    'use strict';

    // -------------------------------------------------------------------------
    // Color palettes
    // -------------------------------------------------------------------------

    // Planet type codes (2-char) → { bands, polar?, glow?, atmoColor? }
    // bands: array of hex colors cycling south→north across latitude bands
    const PLANET_PALETTES = {
        TE: { bands: ['#c8e8d0', '#4a8a60', '#2a6099', '#3d7a52', '#c8a870', '#2a6099', '#4a8a60', '#c8e8d0'], polar: '#e8f0f8', atmoColor: '#4488cc' },
        SE: { bands: ['#5a9a70', '#2a6099', '#4a8a60', '#2a6099', '#5a9a70', '#2a6099', '#4a8a60', '#5a9a70'], polar: '#d8eef8', atmoColor: '#5599cc' },
        MP: { bands: ['#8a9890', '#7a8880', '#8a9890', '#7a8880'], atmoColor: null },
        SI: { bands: ['#888880', '#707870', '#888880', '#707870', '#909890'], atmoColor: null },
        CT: { bands: ['#3a3030', '#4a3828', '#3a3030', '#4a3828', '#3a3030'], atmoColor: null },
        GG: { bands: ['#c87941', '#d4a056', '#8b5a2b', '#d4a056', '#c87941', '#8b5a2b', '#d4a056', '#c87941'], atmoColor: null },
        IG: { bands: ['#5b8db8', '#7aa5c8', '#3a6a8a', '#7aa5c8', '#5b8db8', '#3a6a8a'], atmoColor: '#88bbdd' },
        AB: { bands: ['#606060', '#484840', '#606060', '#484840'], atmoColor: null },
    };

    // Moon type codes (1-char) → palette
    const MOON_PALETTES = {
        R: { bands: ['#888070', '#706858', '#888070', '#706858', '#888070'], atmoColor: null },
        I: { bands: ['#c8d8e8', '#b8c8d8', '#d8e8f8', '#b8c8d8', '#c8d8e8'], polar: '#e8f0f8', atmoColor: null },
        O: { bands: ['#c8a870', '#b89860', '#c8a870', '#a88850', '#c8a870'], atmoColor: '#aaccee' },
        T: { bands: ['#c8e8d0', '#4a8a60', '#2a6099', '#4a8a60', '#c8e8d0'], polar: '#e8f0f8', atmoColor: '#4488cc' },
    };

    // Star spectral type → body color
    const STAR_COLORS = {
        O: '#aaccff', B: '#bbccff', A: '#ddeeff', F: '#ffffee',
        G: '#ffe880', K: '#ffaa44', M: '#ff6622', L: '#cc4411',
        T: '#882200', Y: '#441100', D: '#ccddff', WR: '#88ccff',
    };

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    function hexToRgb(hex) {
        const m = hex.replace('#', '').match(/.{2}/g);
        return m ? [parseInt(m[0], 16), parseInt(m[1], 16), parseInt(m[2], 16)] : [128, 128, 128];
    }

    function lerpRgb(a, b, t) {
        return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
    }

    // Fixed light direction: normalize(-1, -1, 2) — upper-left-front
    const LX = -0.4082, LY = -0.4082, LZ = 0.8165;

    // -------------------------------------------------------------------------
    // PlanetGlobe class
    // -------------------------------------------------------------------------

    class PlanetGlobe {
        constructor(canvas) {
            this.canvas = canvas;
            this.ctx = canvas.getContext('2d');
            this.W = canvas.width;
            this.H = canvas.height;
            this.phase = 0.0;
            this.animHandle = null;
            this.objectType = null;
            this.palette = null;
            this.starColor = null;
            this.hasAtmo = false;
        }

        /**
         * Configure the globe for a new object from the API response payload.
         * @param {Object} data  The JSON object returned by /api/universe/<type>/<id>/
         */
        setObject(data) {
            this.phase = 0.0;
            const typeCode = (data.type_code || '').toLowerCase();
            this.objectType = typeCode;
            this.palette = null;
            this.starColor = null;
            this.hasAtmo = !!data.has_atmosphere;

            if (typeCode === 'planet') {
                this.palette = PLANET_PALETTES[data.planet_type_code] || PLANET_PALETTES['SI'];
            } else if (typeCode === 'moon') {
                this.palette = MOON_PALETTES[data.moon_type_code] || MOON_PALETTES['R'];
            } else if (typeCode === 'star') {
                this.starColor = STAR_COLORS[data.star_type] || STAR_COLORS['G'];
            }
        }

        /** Render one frame at the current phase angle. */
        render() {
            this.ctx.clearRect(0, 0, this.W, this.H);
            if (this.objectType === 'star') {
                this._renderStar();
            } else if (this.palette) {
                this._renderPlanet();
            }
        }

        _renderPlanet() {
            const { ctx, W, H, phase, palette, hasAtmo } = this;
            const cx = W / 2, cy = H / 2;
            const R = Math.min(W, H) / 2 - 4;

            const bandRgbs = palette.bands.map(hexToRgb);
            const nBands = bandRgbs.length;
            const polarRgb = palette.polar ? hexToRgb(palette.polar) : null;
            const glowRgb = palette.glow ? hexToRgb(palette.glow) : null;
            const cosP = Math.cos(phase), sinP = Math.sin(phase);

            // --- Raytrace sphere into ImageData ---
            const imgData = ctx.createImageData(W, H);
            const pix = imgData.data;

            for (let py = 0; py < H; py++) {
                const dy = (py - cy) / R;
                const dy2 = dy * dy;
                for (let px = 0; px < W; px++) {
                    const dx = (px - cx) / R;
                    const r2 = dx * dx + dy2;
                    if (r2 > 1.0) continue;

                    const dz = Math.sqrt(1.0 - r2);

                    // Lambertian diffuse + ambient
                    const diff = Math.max(0, LX * dx + LY * dy + LZ * dz);
                    const intensity = 0.12 + diff * 0.88;

                    // Y-axis rotation for spin
                    const rx = dx * cosP + dz * sinP;
                    const rz = -dx * sinP + dz * cosP;
                    const lon = Math.atan2(rx, rz > 0.001 ? rz : 0.001);

                    // Latitude band + slight longitudinal wobble for cloud texture
                    const lat = dy;
                    let rgb;
                    if (polarRgb && Math.abs(lat) > 0.82) {
                        const t = Math.min(1, (Math.abs(lat) - 0.82) / 0.18);
                        const bi = Math.floor(((lat + 1) / 2) * nBands) % nBands;
                        rgb = lerpRgb(bandRgbs[bi], polarRgb, t);
                    } else {
                        const wobble = Math.sin(lon * 4 + phase * 0.2) * 0.05;
                        const bandT = (((lat + 1) / 2 + wobble) % 1 + 1) % 1;
                        const bif = bandT * nBands;
                        const b0 = Math.floor(bif) % nBands;
                        const b1 = (b0 + 1) % nBands;
                        rgb = lerpRgb(bandRgbs[b0], bandRgbs[b1], bif - b0);
                    }

                    let r, g, b;
                    if (glowRgb) {
                        // Lava/volcanic: add red-hot emission in shadow
                        const emit = 0.35 * (1.0 - diff);
                        r = Math.min(255, rgb[0] * intensity + glowRgb[0] * emit);
                        g = Math.min(255, rgb[1] * intensity + glowRgb[1] * emit);
                        b = Math.min(255, rgb[2] * intensity + glowRgb[2] * emit);
                    } else {
                        r = rgb[0] * intensity;
                        g = rgb[1] * intensity;
                        b = rgb[2] * intensity;
                    }

                    const idx = (py * W + px) * 4;
                    pix[idx] = r; pix[idx + 1] = g; pix[idx + 2] = b; pix[idx + 3] = 255;
                }
            }
            ctx.putImageData(imgData, 0, 0);

            // --- Atmosphere limb glow (outside sphere edge) ---
            if (hasAtmo && palette.atmoColor) {
                const [ar, ag, ab] = hexToRgb(palette.atmoColor);
                const grad = ctx.createRadialGradient(cx, cy, R - 1, cx, cy, R + 5);
                grad.addColorStop(0, `rgba(${ar},${ag},${ab},0)`);
                grad.addColorStop(0.4, `rgba(${ar},${ag},${ab},0.4)`);
                grad.addColorStop(1, `rgba(${ar},${ag},${ab},0)`);
                ctx.beginPath();
                ctx.arc(cx, cy, R + 5, 0, Math.PI * 2);
                ctx.fillStyle = grad;
                ctx.fill();
            }

            // --- Specular highlight (clipped to sphere circle) ---
            ctx.save();
            ctx.beginPath();
            ctx.arc(cx, cy, R, 0, Math.PI * 2);
            ctx.clip();
            const specGrad = ctx.createRadialGradient(
                cx - R * 0.28, cy - R * 0.28, 0,
                cx - R * 0.1, cy - R * 0.1, R * 0.55
            );
            specGrad.addColorStop(0, 'rgba(255,255,255,0.22)');
            specGrad.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.fillStyle = specGrad;
            ctx.fillRect(0, 0, W, H);
            ctx.restore();
        }

        _renderStar() {
            const { ctx, W, H, phase, starColor } = this;
            const cx = W / 2, cy = H / 2;
            const baseR = Math.min(W, H) / 2 - 6;
            // Slight pulsation
            const R = baseR * (1 + 0.025 * Math.sin(phase * 2.5));
            const [sr, sg, sb] = hexToRgb(starColor);

            // Outer corona
            const corona = ctx.createRadialGradient(cx, cy, R * 0.5, cx, cy, R * 2.2);
            corona.addColorStop(0, `rgba(${sr},${sg},${sb},0.30)`);
            corona.addColorStop(0.4, `rgba(${sr},${sg},${sb},0.10)`);
            corona.addColorStop(1, `rgba(${sr},${sg},${sb},0)`);
            ctx.beginPath();
            ctx.arc(cx, cy, R * 2.2, 0, Math.PI * 2);
            ctx.fillStyle = corona;
            ctx.fill();

            // Star body with off-centre highlight
            const body = ctx.createRadialGradient(cx - R * 0.25, cy - R * 0.25, 0, cx, cy, R);
            body.addColorStop(0, `rgb(${Math.min(255, sr + 70)},${Math.min(255, sg + 70)},${Math.min(255, sb + 70)})`);
            body.addColorStop(0.65, `rgb(${sr},${sg},${sb})`);
            body.addColorStop(1, `rgb(${Math.round(sr * 0.5)},${Math.round(sg * 0.5)},${Math.round(sb * 0.5)})`);
            ctx.beginPath();
            ctx.arc(cx, cy, R, 0, Math.PI * 2);
            ctx.fillStyle = body;
            ctx.fill();
        }

        /** Start the animation loop. Safe to call repeatedly. */
        startAnimation() {
            if (this.animHandle !== null) return;
            const loop = () => {
                this.phase += 0.012;
                this.render();
                this.animHandle = requestAnimationFrame(loop);
            };
            this.animHandle = requestAnimationFrame(loop);
        }

        /** Stop the animation loop and release the rAF handle. */
        stopAnimation() {
            if (this.animHandle !== null) {
                cancelAnimationFrame(this.animHandle);
                this.animHandle = null;
            }
        }
    }

    window.PlanetGlobe = PlanetGlobe;
}());
