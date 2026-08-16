import { useCallback, useEffect, useRef, useState } from "react";
import Avatar from "./Avatar.jsx";
import {
  BEARD,
  BROW_SHAPE_ITEMS,
  BROW_THICKNESS,
  CLOTHES,
  CLOTHES_COLORS,
  EYES,
  GLASSES_OPTIONS,
  HAIR_COLORS,
  HAIR_STYLES,
  MOUTH,
  SKIN_COLORS,
} from "../data/avatarOptions.js";
import { FACE_SHAPES } from "../data/customParts.js";

// 카메라로 얼굴을 한 장 찍어 아바타 설정의 '시작점'을 잡는다.
//
// 닮게 만드는 기능이 아니다. 선택지가 5만 조합뿐이라 대부분의 실제 얼굴은 이 안에 없다.
// 그래서 결과를 바로 덮어쓰지 않고 반드시 확인 단계를 거친다 — 사진과 결과를 나란히
// 보여주고, 무엇이 바뀌는지 알려준 뒤, 사용자가 적용/취소를 고른다.
//
// 사진 취급: 프레임은 메모리(state)에만 있고 적용·취소 어느 쪽이든 즉시 버린다.
// 파일이나 localStorage 에 쓰지 않는다. 다만 분석은 서버를 거치므로 기기 밖으로 전송된다.

const FIELD_LABELS = {
  face: "얼굴형",
  hairStyle: "헤어스타일",
  hairColor: "헤어 컬러",
  skinColor: "피부색",
  eyes: "눈",
  lashes: "속눈썹",
  eyebrows: "눈썹 모양",
  browThickness: "눈썹 굵기",
  mouth: "표정",
  glasses: "안경",
  beard: "수염",
  clothes: "의상",
  clothesColor: "의상 컬러",
  pattern: "옷 무늬",
};

// 백엔드가 고를 수 있는 값 목록. avatarOptions.js 가 원본이라 여기서 파생시킨다.
// 새 헤어스타일을 추가하면 자동으로 후보에 포함된다.
function buildOptions() {
  const ids = (arr) => arr.map((x) => x.id);
  return {
    face: Object.keys(FACE_SHAPES),
    hairStyle: ids(HAIR_STYLES),
    eyes: ids(EYES),
    eyebrows: ids(BROW_SHAPE_ITEMS),
    browThickness: ids(BROW_THICKNESS),
    mouth: ids(MOUTH),
    glasses: ids(GLASSES_OPTIONS),
    beard: [...ids(BEARD), null], // null = 수염 없음
    clothes: ids(CLOTHES),
    skinColor: SKIN_COLORS,
    hairColor: HAIR_COLORS,
    clothesColor: CLOTHES_COLORS,
  };
}

export default function AvatarFromPhoto({ current, onResult, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [status, setStatus] = useState("starting"); // starting | ready | working | review | error
  const [error, setError] = useState(null);
  const [shot, setShot] = useState(null); // 찍은 프레임 (메모리에만)
  const [result, setResult] = useState(null); // 모델이 고른 설정

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startCamera = useCallback(async () => {
    setError(null);
    setStatus("starting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 640 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }
      setStatus("ready");
    } catch {
      setError("카메라를 열 수 없습니다. 브라우저 권한을 확인해주세요.");
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    startCamera();
    return stopCamera; // 화면을 벗어나면 카메라를 반드시 끈다
  }, [startCamera, stopCamera]);

  async function shoot() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    setStatus("working");
    setError(null);
    try {
      // 정사각형으로 가운데를 잘라 640px 로 줄인다(전송량·비용을 줄이려고).
      const side = Math.min(video.videoWidth, video.videoHeight);
      const canvas = document.createElement("canvas");
      canvas.width = 640;
      canvas.height = 640;
      canvas
        .getContext("2d")
        .drawImage(
          video,
          (video.videoWidth - side) / 2,
          (video.videoHeight - side) / 2,
          side,
          side,
          0,
          0,
          640,
          640
        );
      const image = canvas.toDataURL("image/jpeg", 0.85);
      stopCamera(); // 찍는 즉시 카메라를 끈다

      const base = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
      const res = await fetch(`${base}/avatar/from-photo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image, options: buildOptions() }),
      });
      if (!res.ok) {
        let detail = `분석 실패 (${res.status})`;
        try {
          const body = await res.json();
          if (body.detail) detail = body.detail;
        } catch {
          /* 본문이 JSON 이 아니면 상태코드만 */
        }
        throw new Error(detail);
      }
      const { config, face_visible: faceVisible } = await res.json();
      if (faceVisible === false) {
        // 얼굴이 제대로 안 잡힌 결과를 적용하면 엉뚱한 아바타가 된다. 다시 찍게 한다.
        setError("얼굴이 잘 안 보여요. 밝은 곳에서 얼굴을 원 안에 맞춰 다시 찍어주세요.");
        setStatus("error");
        return;
      }
      setShot(image);
      setResult(config);
      setStatus("review"); // 바로 적용하지 않는다
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  }

  function discard() {
    setShot(null);
    setResult(null);
  }

  function apply() {
    onResult?.(result);
    discard();
  }

  function retake() {
    discard();
    startCamera();
  }

  function close() {
    stopCamera();
    discard();
    onClose?.();
  }

  const same = (a, b) =>
    typeof a === "object" || typeof b === "object" ? JSON.stringify(a) === JSON.stringify(b) : a === b;
  const changed = result
    ? Object.keys(result).filter((k) => FIELD_LABELS[k] && !same(result[k], current?.[k]))
    : [];

  return (
    <div className="mt-3 rounded-2xl border border-violet-400/20 bg-[#0B1423] p-3">
      <div className="flex items-center justify-between">
        <strong className="text-[12px] text-ink">카메라로 맞추기</strong>
        <button type="button" onClick={close} className="tap text-[11px] text-sub">
          닫기
        </button>
      </div>

      {status === "review" ? (
        <>
          <p className="mt-2 text-[11px] text-sub">이렇게 시작해볼까요?</p>
          <div className="mt-2 flex items-center justify-center gap-3">
            <figure className="m-0 text-center">
              <img
                src={shot}
                alt="방금 찍은 사진"
                className="h-[104px] w-[104px] rounded-xl object-cover"
                style={{ transform: "scaleX(-1)" }}
              />
              <figcaption className="mt-1 text-[9px] text-mut">사진</figcaption>
            </figure>
            <span className="text-[16px] text-mut">→</span>
            <figure className="m-0 text-center">
              <Avatar config={{ ...current, ...result }} size={104} ring={false} />
              <figcaption className="mt-1 text-[9px] text-mut">아바타</figcaption>
            </figure>
          </div>

          <p className="mt-2 text-[10px] leading-relaxed text-mut">
            {changed.length
              ? `바뀌는 항목 ${changed.length}개 · ${changed.map((k) => FIELD_LABELS[k]).join(" · ")}`
              : "바뀌는 항목이 없습니다."}
            <br />
            선택지가 정해져 있어서 똑같이 생기진 않습니다. 적용한 뒤 화살표로 고치시면 됩니다.
          </p>

          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={apply}
              className="tap flex-1 rounded-xl border border-violet-400/25 bg-violet-500/15 py-2.5 text-[12px] font-semibold text-violet-200"
            >
              적용하기
            </button>
            <button
              type="button"
              onClick={retake}
              className="tap rounded-xl border border-white/10 bg-white/[.04] px-3 py-2.5 text-[12px] text-sub"
            >
              다시 찍기
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="relative mt-2 overflow-hidden rounded-xl bg-black/40">
            <video
              ref={videoRef}
              playsInline
              muted
              className="block h-[260px] w-full object-cover"
              style={{ transform: "scaleX(-1)" }} // 거울처럼 보이게
            />
            {/* 얼굴 맞추는 가이드. 이 안에 얼굴을 채우면 잘린 사진이 줄어든다. */}
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="h-[200px] w-[155px] rounded-[50%] border-2 border-dashed border-violet-300/60 shadow-[0_0_0_9999px_rgba(0,0,0,.35)]" />
            </div>
            <p className="pointer-events-none absolute inset-x-0 bottom-1.5 text-center text-[10px] text-white/80">
              얼굴을 원 안에 맞춰주세요
            </p>
          </div>

          {error && <p className="mt-2 text-[11px] text-danger">{error}</p>}

          <button
            type="button"
            onClick={status === "error" ? startCamera : shoot}
            disabled={status === "working"}
            className="tap mt-2 w-full rounded-xl border border-violet-400/25 bg-violet-500/15 py-2.5 text-[12px] font-semibold text-violet-200 disabled:opacity-50"
          >
            {status === "working" ? "분석 중…" : status === "error" ? "다시 시도" : "이 얼굴로 맞추기"}
          </button>

          <p className="mt-2 text-[10px] leading-relaxed text-mut">
            사진은 저장되지 않습니다. 분석에만 쓰고 바로 버립니다.
            <br />
            다만 분석은 서버를 거치므로 사진이 기기 밖으로 전송됩니다.
          </p>
        </>
      )}
    </div>
  );
}
