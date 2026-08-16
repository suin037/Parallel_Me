import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls, Sparkles, useTexture } from "@react-three/drei";
import * as THREE from "three";
import { RotateCcw } from "lucide-react";
import { seedFrom, starShapeFor } from "../data/starShapes.js";
import { PLANET_TEXTURES, seeded, SURFACE } from "../data/planetSurface.js";

// 배치 — 크기·깊이를 다르게 줘 화면이 평평해 보이지 않게 한다.
// 진로(고리 보라) 왼쪽 위 · 삶의 만족(테라코타, 가장 큼) 왼쪽 아래 · 관계(붉은 암석)
// 가운데 빈 곳 · 건강(청록, 가장 작음) 오른쪽 아래 · 성장성(파랑) 오른쪽 위.
const PLANET_POSITIONS = [
  [-4.15, 1.85, -1.0], [-1.7, -1.75, 1.5], [.7, 1.15, -5.4],
  [3.95, -2.15, -.9], [4.25, 1.8, -3.3],
];
const PLANET_SIZES = [1.05, 1.5, .95, .82, 1.15];
const INITIAL_CAMERA = new THREE.Vector3(0, 3.7, 14.4);
const INTRO_CAMERA = new THREE.Vector3(0, 8.2, 27.5);
const UNIVERSE_TARGET = new THREE.Vector3(0, -1.1, 0);

// 행성은 매 프레임 제 궤도를 돈다. 별자리·시나리오도 반드시 같은 식을 써야 행성을 따라간다.
// (전에는 이 셋이 PLANET_POSITIONS 를 '고정 위치'로 읽어, 행성만 궤도를 돌고 별자리는
//  출발 자리에 남았다. 몇 분만 지나도 별자리가 행성과 떨어져 엉뚱한 데 떠 있었다.)
function planetPositionAt(index, time, out = new THREE.Vector3()) {
  const base = PLANET_POSITIONS[index] || PLANET_POSITIONS[0];
  const radius = Math.hypot(base[0], base[2]);
  const angle = Math.atan2(base[2], base[0]) + time * (.0045 + index * .00035);
  return out.set(
    Math.cos(angle) * radius,
    base[1] + Math.sin(time * .22 + index) * .06,
    Math.sin(angle) * radius,
  );
}

function makeSoftTexture(stops) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 256;
  const context = canvas.getContext("2d");
  const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128);
  stops.forEach(([position, color]) => gradient.addColorStop(position, color));
  context.fillStyle = gradient;
  context.fillRect(0, 0, 256, 256);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// 별 알갱이 — Points 로 한 번에 그리므로 모양은 이 스프라이트가 낸다.
// 모듈에 한 번만 만든다(별자리마다 캔버스를 만들면 그것도 비용이다).
let _starSprite = null;
function starSprite() {
  if (_starSprite) return _starSprite;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(.35, "rgba(255,255,255,.72)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  _starSprite = new THREE.CanvasTexture(canvas);
  _starSprite.colorSpace = THREE.SRGBColorSpace;
  return _starSprite;
}

function Nebulae({ reduced }) {
  const texture = useMemo(() => makeSoftTexture([
    [0, "rgba(91,111,210,.24)"], [.28, "rgba(67,51,147,.16)"],
    [.62, "rgba(35,23,91,.07)"], [1, "rgba(0,0,0,0)"],
  ]), []);
  const warm = useMemo(() => makeSoftTexture([
    [0, "rgba(255,213,155,.18)"], [.22, "rgba(152,93,143,.10)"], [1, "rgba(0,0,0,0)"],
  ]), []);
  const clouds = reduced ? [[-9,5,-18,18,8,texture],[10,-5,-24,23,10,texture]] : [
    [-11,6,-20,22,9,texture],[12,-6,-27,27,12,texture],[-3,-9,-15,16,7,warm],[5,9,-32,22,9,texture],
  ];
  return <group>{clouds.map(([x,y,z,w,h,map],index)=><sprite key={index} position={[x,y,z]} scale={[w,h,1]}>
    <spriteMaterial map={map} transparent opacity={.7} depthWrite={false} blending={THREE.AdditiveBlending}/>
  </sprite>)}</group>;
}

function Galaxy({ reduced }) {
  const ref = useRef();
  const geometry = useMemo(() => {
    const count = reduced ? 3000 : 7200;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const random = seeded(17.31);
    const inner = new THREE.Color("#fff4dc"), outer = new THREE.Color("#7557ba");
    for (let i = 0; i < count; i++) {
      const radius = Math.pow(random(), .72) * 9.8;
      const arm = i % 4;
      const angle = arm * Math.PI / 2 + radius * .78 + (random() - .5) * (.3 + radius * .07);
      const spread = .08 + radius * .045;
      positions[i * 3] = Math.cos(angle) * radius + (random() - .5) * spread;
      positions[i * 3 + 1] = (random() - .5) * (.28 + radius * .075);
      positions[i * 3 + 2] = Math.sin(angle) * radius + (random() - .5) * spread;
      const color = inner.clone().lerp(outer, Math.min(1, radius / 8.8));
      color.offsetHSL((random() - .5) * .035, 0, (random() - .5) * .12);
      colors.set(color.toArray(), i * 3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return geo;
  }, [reduced]);
  useFrame((_, delta) => { if (ref.current) ref.current.rotation.y += delta * .012; });
  const core = useMemo(() => makeSoftTexture([[0,"rgba(255,247,217,.95)"],[.12,"rgba(255,219,162,.45)"],[.42,"rgba(147,112,214,.12)"],[1,"rgba(0,0,0,0)"]]), []);
  // 배치는 그대로 둔다(뒤로 밀면 은하가 작고 밋밋해진다). 대신 밝기를 낮춰
  // 별자리·행성이 그 위에 묻히지 않게 한다 — 겹침은 위치가 아니라 대비 문제였다.
  return <group rotation={[-.36, 0, .12]} position={[0,-.3,-3]}>
    <points ref={ref} geometry={geometry}>
      <pointsMaterial size={reduced ? .024 : .032} vertexColors transparent opacity={.5} sizeAttenuation depthWrite={false} blending={THREE.AdditiveBlending}/>
    </points>
    <sprite scale={[4.6,4.6,1]}><spriteMaterial map={core} transparent opacity={.42} depthWrite={false} blending={THREE.AdditiveBlending}/></sprite>
    <pointLight color="#ffe3ba" intensity={7} distance={12}/>
  </group>;
}

function StarLayer({ count, radius, size, opacity, seed, color="#e9ecff" }) {
  const geometry = useMemo(() => {
    const random = seeded(seed), positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = radius * (.55 + random() * .45), theta = random() * Math.PI * 2, phi = Math.acos(2 * random() - 1);
      positions.set([r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi) * .62, r * Math.sin(phi) * Math.sin(theta)], i * 3);
    }
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(positions, 3)); return geo;
  }, [count, radius, seed]);
  const ref = useRef();
  useFrame((state) => { if (ref.current) ref.current.material.opacity = opacity * (.92 + Math.sin(state.clock.elapsedTime * .38 + seed) * .08); });
  return <points ref={ref} geometry={geometry}><pointsMaterial color={color} size={size} transparent opacity={opacity} sizeAttenuation depthWrite={false}/></points>;
}

// 궤도선 — 임의의 반지름이 아니라 행성이 실제로 도는 반지름에 긋는다.
// 그래야 행성이 선 위를 지나간다(전에는 선과 행성이 따로 놀았다).
function OrbitRings() {
  const radii = useMemo(() => {
    const seen = PLANET_POSITIONS.map((p) => Math.hypot(p[0], p[2]));
    // 반지름이 거의 같으면 선이 겹쳐 두꺼운 띠로 보인다 — 하나만 남긴다.
    return seen.sort((a, b) => a - b).filter((r, i, all) => i === 0 || r - all[i - 1] > .25);
  }, []);
  return <group rotation={[-Math.PI / 2 + .19, 0, .1]}>{radii.map((r,i)=><mesh key={r} rotation={[0,i*.025,i*.018]}><ringGeometry args={[r-.005,r+.005,192]}/><meshBasicMaterial color="#8f8eb0" transparent opacity={.05+i*.006} side={THREE.DoubleSide} depthWrite={false}/></mesh>)}</group>;
}

// 장식용 celestial atlas. 기록 별자리와 모양을 공유하면 7별 뼈대(특히 북두칠성)가
// 화면 전체에 반복된다. 배경은 서로 다른 실루엣만 사용하고, 기록 별자리는 아래의
// Constellation3D가 기존 데이터 규칙대로 별도로 그린다.
const CELESTIAL_ATLAS = [
  { id:"lyra", points:[[-1,-.25],[-.45,.7],[.05,.35],[.55,.82],[1,-.15],[.2,-.65]], edges:[[0,1],[1,2],[2,3],[3,4],[4,5],[5,2]] },
  { id:"phoenix", points:[[-1,.05],[-.35,.22],[0,.9],[.25,.18],[1,.45],[.52,-.18],[.1,-.82],[-.42,-.42]], edges:[[0,1],[1,2],[1,3],[3,4],[3,5],[5,6],[5,7],[7,1]] },
  { id:"serpens", points:[[-1,.6],[-.7,.1],[-.28,.35],[.05,-.08],[.42,.18],[.68,-.48],[1,-.22]], edges:[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6]] },
  { id:"vela", points:[[-.9,-.55],[-.7,.55],[-.05,.9],[.75,.48],[.95,-.5],[.05,-.18]], edges:[[0,1],[1,2],[2,3],[3,4],[4,0],[1,5],[5,3]] },
  { id:"corona", points:[[-1,.18],[-.72,-.35],[-.28,-.68],[.2,-.62],[.65,-.28],[1,.32]], edges:[[0,1],[1,2],[2,3],[3,4],[4,5]] },
  { id:"grus", points:[[-.85,.78],[-.28,.2],[.05,-.82],[.2,.12],[.9,.65],[.55,.02],[.96,-.52]], edges:[[0,1],[1,2],[1,3],[3,4],[3,5],[5,6]] },
  { id:"harp", points:[[-.75,.72],[.5,.92],[.9,.15],[.38,-.7],[-.62,-.55],[-.05,.15]], edges:[[0,1],[1,2],[2,3],[3,4],[4,0],[0,5],[5,2],[5,4]] },
  { id:"kite", points:[[0,.95],[-.72,.12],[0,-.42],[.75,.08],[.18,-.92]], edges:[[0,1],[1,2],[2,3],[3,0],[2,4]] },
  { id:"river", points:[[-1,.7],[-.68,.2],[-.82,-.28],[-.28,-.12],[.08,-.65],[.48,-.18],[.9,-.38],[1,.18]], edges:[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7]] },
  { id:"twins", points:[[-.72,.82],[-.48,.18],[-.78,-.65],[-.05,-.05],[.48,.25],[.78,.88],[.72,-.62]], edges:[[0,1],[1,2],[1,3],[3,4],[4,5],[4,6]] },
  { id:"altar", points:[[-.9,.5],[-.35,.72],[.35,.68],[.88,.35],[.55,-.5],[0,-.78],[-.58,-.42]], edges:[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,0],[1,6],[2,4]] },
  { id:"wing", points:[[-1,-.12],[-.4,.08],[-.05,.72],[.18,.08],[.95,.45],[.58,-.08],[.12,-.68]], edges:[[0,1],[1,2],[1,3],[3,4],[3,5],[3,6]] },
  { id:"compass", points:[[0,.95],[.25,.25],[.9,0],[.2,-.18],[0,-.92],[-.22,-.2],[-.92,0],[-.2,.2]], edges:[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7],[7,0],[1,5],[3,7]] },
  { id:"branch", points:[[-.95,-.58],[-.55,-.08],[-.1,.12],[.35,.42],[.92,.22],[-.15,.72],[.4,-.38],[.85,-.72]], edges:[[0,1],[1,2],[2,3],[3,4],[2,5],[2,6],[6,7]] },
];

function BackdropConstellations({ count = 14 }) {
  const figures = useMemo(() => {
    const random = seeded(4.77);
    return CELESTIAL_ATLAS.slice(0, count).map((shape, i) => {
      const theta = random() * Math.PI * 2;
      const phi = Math.acos(2 * random() - 1);
      const r = 26 + random() * 12;
      const scale = 1.8 + random() * 2.1;
      const pts = shape.points.map(([x, y]) => [x * scale, y * scale, 0]);
      const line = new THREE.BufferGeometry();
      line.setAttribute("position", new THREE.Float32BufferAttribute(
        shape.edges.flatMap(([a, b]) => [...pts[a], ...pts[b]]), 3));
      const dots = new THREE.BufferGeometry();
      dots.setAttribute("position", new THREE.Float32BufferAttribute(pts.flat(), 3));
      return {
        key: `${i}-${shape.id}`, line, dots,
        position: [r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi) * .55, r * Math.sin(phi) * Math.sin(theta)],
        rotation: (random() - .5) * 1.5,
        color: i % 4 === 0 ? "#e6c98f" : "#bac8e8",
        halo: i === 1 || i === 8 || i === 12,
        haloSize: scale * (1.12 + random() * .28),
      };
    });
  }, [count]);
  return <group>{figures.map((f)=><group key={f.key} position={f.position} onUpdate={(g)=>g.lookAt(0,0,0)}>
    <group rotation={[0,0,f.rotation]}>
    {/* 장식이다. 기록 별자리(Constellation3D)와 생김새가 같아서 세기까지 비슷하면
        사용자가 둘을 구분할 수 없다 — 반드시 기록 쪽보다 확실히 어두워야 한다. */}
    <lineSegments geometry={f.line}><lineBasicMaterial color={f.color} transparent opacity={.07} depthWrite={false}/></lineSegments>
    <points geometry={f.dots}><pointsMaterial color={f.color} size={.2} sizeAttenuation transparent opacity={.32} map={starSprite()} depthWrite={false} blending={THREE.AdditiveBlending}/></points>
    {f.halo && <>
      <mesh><ringGeometry args={[f.haloSize,f.haloSize+.012,96]}/><meshBasicMaterial color="#d4b77b" transparent opacity={.075} side={THREE.DoubleSide} depthWrite={false}/></mesh>
      <mesh rotation={[0,0,.55]}><ringGeometry args={[f.haloSize*.72,f.haloSize*.72+.009,72,1,0,Math.PI*1.42]}/><meshBasicMaterial color="#d4b77b" transparent opacity={.09} side={THREE.DoubleSide} depthWrite={false}/></mesh>
    </>}
    </group>
  </group>)}</group>;
}

function Planet({ planet, index, selected, onSelect, skin }) {
  const group = useRef();
  const mesh = useRef();
  const position = PLANET_POSITIONS[index];
  const size = PLANET_SIZES[index];
  const selectPlanet = (event) => { event.stopPropagation(); onSelect(planet.key); };
  const showPointer = (event) => { event.stopPropagation(); document.body.style.cursor = "pointer"; };
  const hidePointer = () => { document.body.style.cursor = ""; };
  const kind = planet.kind || "gas";
  const surface = SURFACE[kind] || SURFACE.gas;
  const sourceTexture = useTexture(PLANET_TEXTURES[planet.key]);
  const texture = useMemo(() => {
    sourceTexture.wrapS = THREE.RepeatWrapping;
    sourceTexture.colorSpace = THREE.SRGBColorSpace;
    sourceTexture.anisotropy = 8;
    sourceTexture.needsUpdate = true;
    return sourceTexture;
  }, [sourceTexture]);
  useFrame((state, delta) => {
    if (mesh.current) mesh.current.rotation.y += delta * (.028 + index * .004);
    if (group.current) planetPositionAt(index, state.clock.elapsedTime, group.current.position);
  });
  return <group ref={group} position={position}>
    <mesh onClick={selectPlanet} onDoubleClick={selectPlanet} onPointerOver={showPointer} onPointerOut={hidePointer}>
      <sphereGeometry args={[Math.max(size * 1.65, 1.65), 24, 24]}/>
      <meshBasicMaterial transparent opacity={0} depthWrite={false}/>
    </mesh>
    <mesh ref={mesh} onClick={selectPlanet} onDoubleClick={selectPlanet} onPointerOver={showPointer} onPointerOut={hidePointer}>
      <sphereGeometry args={[size, 64, 64]}/>
      <meshPhysicalMaterial
        map={texture}
        bumpMap={texture}
        bumpScale={surface.bump}
        color="#ffffff"
        roughness={skin === "glow" ? surface.roughness * .7 : surface.roughness}
        metalness={surface.metalness}
        clearcoat={skin === "glow" ? surface.clearcoat + .2 : surface.clearcoat}
        clearcoatRoughness={.28}
        sheen={kind === "rocky" ? 0 : .2}
        sheenColor={planet.to}
        emissive={planet.from}
        // 자체발광을 낮게 유지해야 밤면이 제대로 어두워지고 명암 경계가 살아난다.
        emissiveIntensity={skin === "glow" ? .05 : selected ? .022 : .006}
      />
    </mesh>
    <mesh scale={1.028}><sphereGeometry args={[size,48,48]}/><meshBasicMaterial color={planet.to} side={THREE.BackSide} transparent opacity={skin === "glow" ? surface.atmos + .04 : surface.atmos} blending={THREE.AdditiveBlending} depthWrite={false}/></mesh>
    {/* 행성마다 달던 점광원과 가짜 하이라이트는 뺐다 — 그 둘이 밤면을 밝혀
        명암 경계를 지우고, 플라스틱 구슬처럼 번들거리게 만들던 원인이다.
        고른 사람만 살짝 밝혀 어느 걸 골랐는지 알 수 있게 남긴다. */}
    {selected && <pointLight position={[-2,2,3]} color={planet.to} intensity={.7} distance={5.5} decay={2}/>}
    {/* 고리는 한 장이 아니라 틈(카시니 간극)을 둔 두 겹이다. 색도 행성색이 아니라
        얼음·먼지에 가까운 옅은 회갈색이어야 '실제 고리'로 읽힌다. */}
    {(index===0||skin==="ring")&&<group rotation={[Math.PI/2.3,.15,0]}>
      <mesh><ringGeometry args={[size*1.22,size*1.38,128]}/><meshBasicMaterial color="#C9BCA8" transparent opacity={.30} side={THREE.DoubleSide} depthWrite={false}/></mesh>
      <mesh><ringGeometry args={[size*1.43,size*1.62,128]}/><meshBasicMaterial color="#9A8E7E" transparent opacity={.19} side={THREE.DoubleSide} depthWrite={false}/></mesh>
    </group>}
    {/* 행성 이름표.
        zIndexRange 를 반드시 낮춰야 한다 — drei 의 Html 은 기본이 1,600만대라
        행성을 눌러 뜨는 패널(z-40)·시트 위로 글씨가 뚫고 올라온다(폰에서 특히
        패널이 화면을 덮어 바로 겹친다). 캔버스 위에는 뜨되 UI 밑에 있게 둔다. */}
    <Html center position={[0,-size-0.5,0]} distanceFactor={10} zIndexRange={[10,0]} style={{pointerEvents:"none"}}><div className={`whitespace-nowrap text-center drop-shadow-[0_2px_8px_#000] ${selected?"text-white":"text-white/80"}`}><b className="text-[13px]">{planet.label}</b></div></Html>
  </group>;
}

const SHAPE_SCALE = .42;   // 뼈대(-1~1)를 행성 옆에 놓기 좋은 크기로

function Constellation3D({ group, index, anchorIndex, onOpen }) {
  const orbit = useRef();
  const figure = useRef();
  // 별자리 하나는 최대 7별로 끊어 넘어온다(starGroupsOf). 여기서 또 자르면 별이 사라진다.
  const visible = group.stars.filter((s)=>!s.empty);
  // 그 행성 안에서 몇 번째 별자리인지로 궤도를 잡는다.
  // 전엔 '전체 배열에서 몇 번째'를 썼는데, 다섯 행성 것이 한 배열로 들어오면서
  // 뒤쪽 별자리가 행성에서 7 이상 떨어져 나가 우주에 흩뿌려진 것처럼 보였다.
  const ord = group.index ?? index;
  const planetSize = PLANET_SIZES[anchorIndex] ?? 1;
  const orbitRadius = planetSize + .75 + (ord % 3) * .3;   // 행성에 붙어 도는 좁은 띠
  // 기록 개수에 맞는 디자인 별자리를 골라 그 자리에 별을 앉힌다.
  const shape = useMemo(
    () => starShapeFor(visible.length, seedFrom(group.weekStart || `${group.domain}-${ord}`)),
    [group.weekStart, group.domain, visible.length, ord],
  );
  const starGeo = useMemo(()=>{
    const g = new THREE.BufferGeometry();
    const xyz = shape.points.slice(0, visible.length)
      .flatMap(([x,y]) => [x * SHAPE_SCALE, y * SHAPE_SCALE, 0]);
    g.setAttribute("position", new THREE.Float32BufferAttribute(xyz, 3));
    return g;
  },[shape, visible.length]);
  // 선은 순번이 아니라 뼈대가 정한 edges 만 긋는다 — 전부를 한 줄로 이으면 실타래가 된다.
  const edgeGeo = useMemo(()=>{
    const g = new THREE.BufferGeometry();
    const xyz = shape.edges.flatMap(([a,b]) =>
      [shape.points[a], shape.points[b]].flatMap(([x,y]) => [x * SHAPE_SCALE, y * SHAPE_SCALE, 0]));
    g.setAttribute("position", new THREE.Float32BufferAttribute(xyz, 3));
    return g;
  },[shape]);
  useFrame((state,delta)=>{
    if (!orbit.current) return;
    // 행성을 따라간다.
    planetPositionAt(anchorIndex, state.clock.elapsedTime, orbit.current.position);
    orbit.current.rotation.y += delta * (.055 + (ord % 5) * .006);
    orbit.current.rotation.z = Math.sin(state.clock.elapsedTime * .08 + ord) * .09;
    // 뼈대는 평면이라 궤도를 돌다 보면 옆으로 서서 사라진다. 늘 카메라를 보게 해
    // 어느 각도에서든 '무슨 모양인지' 읽히게 한다.
    figure.current?.lookAt(state.camera.position);
  });
  if (!visible.length) return null;
  // 황금각(2.4rad)으로 돌려 별자리가 몇 개든 행성 둘레에 고르게 퍼지게 한다.
  return <group ref={orbit} rotation={[.18+(ord%3)*.24, ord*2.39996, .12]}>
    <group position={[orbitRadius,0,0]} onClick={(e)=>{e.stopPropagation();onOpen?.(group);}}>
      <mesh visible={false}><sphereGeometry args={[.5,10,10]}/><meshBasicMaterial transparent opacity={0}/></mesh>
      <group ref={figure}>
        {/* 선이 별자리를 '모양'으로 읽게 하는 유일한 요소다. 예전엔 .2 라 배경의
            장식 별자리(.14)와 세기가 거의 같아, 어느 게 내 기록인지 눈이 구분할
            근거가 없었다. 가산 블렌딩으로 어두운 배경 위에서 선이 발광하게 한다.
            ※ 이 값은 배경(BackdropConstellations·StarLayer)보다 반드시 높아야 한다.
              배경을 밝히려거든 여기도 같이 올릴 것 — 위계가 뒤집히면 원래 문제로 돌아간다. */}
        <lineSegments geometry={edgeGeo}>
          <lineBasicMaterial color="#CBD8F5" transparent opacity={.4}
            blending={THREE.AdditiveBlending} depthWrite={false}/>
        </lineSegments>
        {/* 기록은 하얀 별. 시나리오(마름모)와 한눈에 갈라지도록 색을 섞지 않는다.
            별을 Points 하나로 그린다 — 별마다 mesh + pointLight 를 두면 기록이 늘수록
            드로우콜과 동적 광원이 같이 늘어난다(1년치면 광원만 100개가 넘어 프레임이 무너졌다). */}
        <points geometry={starGeo}>
          <pointsMaterial
            color="#EEF3FF" size={.17} sizeAttenuation transparent opacity={.85}
            map={starSprite()} depthWrite={false} blending={THREE.AdditiveBlending}
          />
        </points>
      </group>
    </group>
  </group>;
}

// 시나리오 = 마름모(정팔면체). 기록(하얀 별)과 모양·색으로 갈라 놓아야
// "지나온 것"과 "탐색한 미래"가 한 행성 위에서 섞이지 않는다.
function ScenarioMark({ scenario, index, anchorIndex, onOpen }) {
  const spin = useRef();
  const root = useRef();
  useFrame((state,delta)=>{
    // 별자리와 마찬가지로 행성을 따라간다.
    if (root.current) planetPositionAt(anchorIndex, state.clock.elapsedTime, root.current.position);
    if (!spin.current) return;
    spin.current.rotation.y += delta * .5;
    spin.current.position.y = Math.sin(state.clock.elapsedTime * .5 + index) * .12;
  });
  const angle = index * 1.9 + .6;
  const radius = 1.62;
  return <group ref={root}>
    <group position={[Math.cos(angle)*radius, 1.15 + (index%2)*.34, Math.sin(angle)*radius]}>
      <mesh ref={spin} onClick={(e)=>{e.stopPropagation();onOpen?.(scenario);}}>
        <octahedronGeometry args={[.135,0]}/>
        <meshStandardMaterial color="#C9A6FF" emissive="#8B6CCF" emissiveIntensity={2.4} roughness={.3}/>
      </mesh>
    </group>
  </group>;
}

function UniverseIntro({ controlsRef, reducedMotion, onComplete }) {
  const { camera } = useThree();
  const elapsed = useRef(0);
  const initialized = useRef(false);

  useFrame((_, delta)=>{
    const controls = controlsRef.current;
    if (!controls) return;

    if (!initialized.current) {
      initialized.current = true;
      if (reducedMotion) {
        camera.position.copy(INITIAL_CAMERA);
        controls.target.copy(UNIVERSE_TARGET);
        controls.update();
        onComplete?.();
        return;
      }
      camera.position.copy(INTRO_CAMERA);
      controls.target.set(0, .35, 0);
      controls.enabled = false;
      controls.update();
    }

    if (reducedMotion || elapsed.current >= 2.8) return;
    elapsed.current = Math.min(2.8, elapsed.current + delta);
    const progress = elapsed.current / 2.8;
    const eased = progress < .5
      ? 4 * progress * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 3) / 2;
    camera.position.lerpVectors(INTRO_CAMERA, INITIAL_CAMERA, eased);
    controls.target.lerpVectors(new THREE.Vector3(0, .35, 0), UNIVERSE_TARGET, eased);
    controls.update();

    if (progress >= 1) {
      camera.position.copy(INITIAL_CAMERA);
      controls.target.copy(UNIVERSE_TARGET);
      controls.enabled = true;
      controls.update();
      onComplete?.();
    }
  });
  return null;
}

function CameraRig({ selectedKey, planets, controlsRef, resetSignal, enabled }) {
  const { camera, clock } = useThree();
  const flight = useRef(null);
  useEffect(()=>{
    if (!enabled) return;
    const index = planets.findIndex((p)=>p.key===selectedKey);
    // 고정 좌표가 아니라 '지금 그 행성이 있는 자리'로 날아간다 — 행성은 궤도를 돌기 때문에
    // 출발 좌표를 쓰면 시간이 지날수록 빈 우주를 비춘다.
    const target = index >= 0 ? planetPositionAt(index, clock.elapsedTime) : UNIVERSE_TARGET.clone();
    // 선택된 행성이 화면 중앙보다 살짝 위에 놓이도록 시선 중심을 아래로 내린다.
    if (index >= 0) target.y -= .9;
    const direction = camera.position.clone().sub(target).normalize();
    flight.current = { target, position: index>=0 ? target.clone().add(direction.multiplyScalar(12)) : INITIAL_CAMERA.clone() };
  },[selectedKey, resetSignal, enabled]);
  useFrame((_, delta)=>{
    if (!flight.current || !controlsRef.current) return;
    const cameraEase = 1 - Math.exp(-delta * 10.5);
    const targetEase = 1 - Math.exp(-delta * 12.5);
    camera.position.lerp(flight.current.position, cameraEase);
    controlsRef.current.target.lerp(flight.current.target, targetEase);
    controlsRef.current.update();
    if (camera.position.distanceTo(flight.current.position)<.018) {
      camera.position.copy(flight.current.position);
      controlsRef.current.target.copy(flight.current.target);
      flight.current=null;
    }
  });
  return null;
}

function Scene({ planets, groups, scenarios = [], selectedKey, onPlanetSelect, onConstellationOpen, onScenarioOpen, resetSignal, reduced, skin }) {
  const controls = useRef();
  const [introDone, setIntroDone] = useState(false);
  const reducedMotion = typeof window!=="undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const selectedIndex = Math.max(0, planets.findIndex((planet)=>planet.key===selectedKey));
  return <>
    <color attach="background" args={["#01030a"]}/><fog attach="fog" args={["#02050d",20,58]}/>
    {/* 천체 조명 — 광원은 사실상 하나(항성). 채움광을 세게 주면 밤면이 사라져
        구가 원판처럼 보인다. 밤면이 검게 죽지 않을 만큼만 남긴다. */}
    <ambientLight color="#46536F" intensity={.10}/>
    <hemisphereLight color="#9fb0dc" groundColor="#04050d" intensity={.14}/>
    <directionalLight position={[-9,10,13]} color="#fff1dc" intensity={3.9}/>
    <Nebulae reduced={reduced}/>
    <StarLayer count={reduced?700:1500} radius={48} size={.025} opacity={.38} seed={2} color="#bfc9e8"/>
    <StarLayer count={reduced?320:760} radius={27} size={.052} opacity={.58} seed={7} color="#e1e8ff"/>
    {/* 가장 가까운 배경 별층. 예전엔 opacity .78 로 기록 별자리의 별(.72)보다 밝아서,
        사용자의 일기가 된 별이 아무 뜻 없는 배경 별에 밀렸다. 배경은 배경답게 물린다. */}
    <StarLayer count={reduced?95:260} radius={14} size={.078} opacity={.52} seed={13} color="#fff5df"/>
    <Sparkles count={reduced?22:48} scale={[25,14,25]} size={.72} speed={.045} opacity={.16} color="#bac8ff" noise={1.8}/>
    <Galaxy reduced={reduced}/><OrbitRings/><BackdropConstellations count={reduced?8:14}/>
    {planets.map((planet,i)=><Planet key={planet.key} planet={planet} index={i} selected={planet.key===selectedKey} onSelect={onPlanetSelect} skin={skin}/>) }
    {/* 자르지 않는다 — 여기서 잘라내면 띄운 별 수가 실제 기록 수와 어긋난다.
        (전에는 .slice(-5) 로 별자리를 5개만 그려 오래된 기록이 조용히 사라졌다.) */}
    {groups.map((group,i)=>{
      const domainIndex=planets.findIndex((planet)=>planet.key===group.domain);
      const anchorIndex=selectedKey?selectedIndex:(domainIndex>=0?domainIndex:i%planets.length);
      return <Constellation3D key={group.weekStart||i} group={group} index={i} anchorIndex={anchorIndex} onOpen={(pickedGroup)=>{
        onPlanetSelect?.(planets[anchorIndex]?.key);
        onConstellationOpen?.(pickedGroup, planets[anchorIndex]?.key);
      }}/>;
    }) }
    {/* 그 영역에서 만든 미래 — 행성 위쪽에 마름모로 뜬다. */}
    {(selectedKey ? scenarios.filter((s)=>s.domain===selectedKey) : scenarios).map((scenario,i)=>{
      const domainIndex=planets.findIndex((planet)=>planet.key===scenario.domain);
      if (domainIndex<0) return null;
      return <ScenarioMark key={`${scenario.domain}-${scenario.date}-${i}`} scenario={scenario} index={i} anchorIndex={domainIndex} onOpen={(picked)=>{
        onPlanetSelect?.(scenario.domain);
        onScenarioOpen?.(picked);
      }}/>;
    }) }
    <OrbitControls ref={controls} target={UNIVERSE_TARGET.toArray()} makeDefault enableDamping dampingFactor={.11} enablePan screenSpacePanning minDistance={2.8} maxDistance={34} rotateSpeed={.22} zoomSpeed={.62} panSpeed={.48} mouseButtons={{LEFT:THREE.MOUSE.ROTATE,MIDDLE:THREE.MOUSE.DOLLY,RIGHT:THREE.MOUSE.PAN}}/>
    <UniverseIntro controlsRef={controls} reducedMotion={reducedMotion} onComplete={()=>setIntroDone(true)}/>
    <CameraRig selectedKey={selectedKey} planets={planets} controlsRef={controls} resetSignal={resetSignal} enabled={introDone}/>
  </>;
}

export default function UniverseMap({ planets, groups=[], scenarios=[], selectedKey, onPlanetSelect, onConstellationOpen, onScenarioOpen, skin="basic" }) {
  const [resetSignal,setResetSignal]=useState(0);
  const reduced = typeof window!=="undefined" && (window.innerWidth<760 || (navigator.hardwareConcurrency||8)<=4);
  return <div className="relative h-[calc(100dvh-112px)] min-h-[540px] w-full overflow-hidden bg-[#01040c] md:h-[calc(100dvh-104px)] md:min-h-[600px]">
    <Canvas dpr={reduced?[1,1.25]:[1,1.75]} camera={{position:INITIAL_CAMERA.toArray(),fov:48,near:.1,far:100}} gl={{antialias:!reduced,powerPreference:"high-performance"}} onPointerMissed={()=>onPlanetSelect?.(null)}>
      <Suspense fallback={null}><Scene planets={planets} groups={groups} scenarios={scenarios} selectedKey={selectedKey} onPlanetSelect={onPlanetSelect} onConstellationOpen={onConstellationOpen} onScenarioOpen={onScenarioOpen} resetSignal={resetSignal} reduced={reduced} skin={skin}/></Suspense>
    </Canvas>
    <div className="pointer-events-none absolute bottom-5 left-1/2 -translate-x-1/2 rounded-full border border-white/10 bg-[#050914]/70 px-4 py-2 text-[9px] tracking-[.08em] text-white/55 backdrop-blur">왼쪽 드래그 회전 · Shift+드래그/오른쪽 드래그 이동 · 휠/핀치 접근</div>
    <button onClick={()=>{onPlanetSelect?.(null);setResetSignal((v)=>v+1);}} className="tap absolute bottom-5 right-5 flex items-center gap-2 rounded-full border border-white/10 bg-[#050914]/75 px-3 text-[10px] text-white/65 backdrop-blur"><RotateCcw size={13}/> 우주 중심</button>
  </div>;
}
