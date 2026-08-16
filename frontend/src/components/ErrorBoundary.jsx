import React from "react";

/**
 * 렌더 중 터진 예외를 잡아 화면에 띄운다.
 *
 * 이게 없으면 React 18 은 루트를 통째로 언마운트해서 #root 가 비고, 결과는
 * 원인을 알 수 없는 흰 화면이다. 아이폰 사파리 — 특히 크로스오리진 iframe
 * 안 — 에서는 콘솔을 볼 방법도 없어서 그대로 미궁에 빠진다.
 *
 * index.html 의 인라인 감시자는 React 가 뜨기 "전"을 맡고, 이 컴포넌트는
 * 뜬 "뒤"를 맡는다. 둘이 붙어야 부팅 구간 전체가 덮인다.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    this.setState({ info });
    // 콘솔이 보이는 환경(PC)에서는 원본 스택이 더 유용하다.
    console.error("[ErrorBoundary]", error, info);
  }

  render() {
    const { error, info } = this.state;
    if (!error) return this.props.children;

    const framed = typeof window !== "undefined" && window.top !== window.self;
    const detail = [
      String(error && error.stack ? error.stack : error),
      info && info.componentStack ? "--- 컴포넌트 ---" + info.componentStack : "",
    ]
      .filter(Boolean)
      .join("\n\n");

    return (
      <div className="min-h-screen bg-[#0B1423] px-[18px] py-[22px] text-[13px] leading-[1.65] text-[#E8EDF6]">
        <p className="mb-1.5 text-[15px] font-bold text-[#FF8A8A]">
          화면을 띄우지 못했습니다
        </p>
        <p className="mb-3.5 text-[12px] text-[#93A0B5]">
          이 화면이 보이면 캡처해서 개발자에게 보내주세요.
        </p>
        <pre className="m-0 whitespace-pre-wrap break-all rounded-[10px] border border-[#22304C] bg-[#101B2E] p-3 text-[11.5px] text-[#C3CCDC]">
          {detail}
        </pre>
        <p className="mt-3.5 text-[11.5px] text-[#7E8BA3]">
          frame={String(framed)} · ua=
          {typeof navigator !== "undefined" ? navigator.userAgent : "?"}
        </p>
      </div>
    );
  }
}
