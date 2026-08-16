// 실제 raster 행성 표면 자산. 각 파일은 구체에 감기도록 만든 2:1 equirectangular PNG다.
// 행성 표면을 canvas, CSS gradient, SVG 또는 단순 crater 도형으로 생성하지 않는다.
export const PLANET_TEXTURES = {
  career: "/planet-textures/career.png",
  life: "/planet-textures/life.png",
  relation: "/planet-textures/relation.png",
  health: "/planet-textures/health.png",
  growth: "/planet-textures/growth.png",
};

// 별·성운 배치에만 쓰는 결정적 난수. 행성 표면 생성과는 무관하다.
export function seeded(seed) {
  let value = seed;
  return () => ((value = Math.sin(value * 999.91) * 43758.5453) - Math.floor(value));
}

// raster 표면 위에 적용하는 최소한의 물리 재질값만 유지한다.
export const SURFACE = {
  gas:   { roughness: .68, metalness: 0,   clearcoat: .06, bump: .006, atmos: .045 },
  ice:   { roughness: .54, metalness: 0,   clearcoat: .14, bump: .004, atmos: .065 },
  ocean: { roughness: .46, metalness: .01, clearcoat: .20, bump: .010, atmos: .085 },
  rocky: { roughness: .94, metalness: 0,   clearcoat: 0,   bump: .045, atmos: .018 },
};
