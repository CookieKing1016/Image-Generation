"""Streamlit showcase and workspace for the Mem2Image prototype."""

from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any, Dict

import streamlit as st

from core import database
from core.metrics import (
    dashboard_totals,
    list_benchmark_run_ids,
    list_failed_items,
    list_turn_badcase_matrix,
    list_turn_metrics,
    summarize_drift_types,
    summarize_methods,
)
from core.orchestrator import Mem2ImageOrchestrator, TurnResult
from core.run_logger import make_run_id
from core.schema import empty_memory
from tools.config import Settings


ROOT = Path(__file__).resolve().parent
HERO_IMAGE_PATH = ROOT / "assets" / "hero-red-scarf-dog.png"


def main() -> None:
    st.set_page_config(
        page_title="Mem2Image | Visual Intent Memory",
        page_icon="◫",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _init_state()
    _inject_styles()
    if st.session_state.page == "workspace":
        settings = _settings_panel()
        _render_workspace(settings)
    elif st.session_state.page == "admin":
        _render_admin_gate()
    else:
        _render_nav()
        _render_hero()
        _render_value_strip()
        _render_memory_section()
        _render_process()
        _render_footer()


def _init_state() -> None:
    defaults = {
        "run_id": make_run_id(),
        "memory": empty_memory(),
        "results": [],
        "last_error": "",
        "page": "home",
        "admin_authenticated": False,
        "admin_error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_state() -> None:
    st.session_state.run_id = make_run_id()
    st.session_state.memory = empty_memory()
    st.session_state.results = []
    st.session_state.last_error = ""


def _settings_panel() -> Settings:
    env_settings = Settings.from_env()
    with st.expander("运行设置", expanded=False):
        first, second, third = st.columns(3)
        with first:
            api_key = st.text_input("SiliconFlow API Key", value=env_settings.api_key, type="password")
            base_url = st.text_input("Base URL", value=env_settings.base_url)
        with second:
            llm_model = st.text_input("LLM Model", value=env_settings.llm_model)
            vlm_model = st.text_input("VLM Model", value=env_settings.vlm_model)
        with third:
            image_model = st.text_input("Image Model", value=env_settings.image_model)
            image_size = st.text_input("Image Size", value=env_settings.image_size)
        st.caption(f"当前运行：{st.session_state.run_id}")
        if st.button("重置当前项目", key="reset_settings"):
            _reset_state()
            st.rerun()
    return Settings(
        api_key=api_key,
        base_url=base_url,
        llm_model=llm_model,
        vlm_model=vlm_model,
        image_model=image_model,
        image_size=image_size,
        num_inference_steps=env_settings.num_inference_steps,
        guidance_scale=env_settings.guidance_scale,
        timeout_seconds=env_settings.timeout_seconds,
    )


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;600;700;800&display=swap');
        :root { --ink:#151515; --muted:#757575; --line:#e9e6e1; --soft:#f8f7f4; --green:#5d9567; }
        .stApp { background:#f4f3f0; color:var(--ink); font-family:"Manrope","Noto Sans SC",sans-serif; }
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"] { background:#fbfaf8; border-right:1px solid var(--line); }
        .block-container { max-width:1200px; padding:1.45rem 2.35rem 0; }
        .value-strip { background:#fff; border:1px solid var(--line); border-radius:10px; }
        .top-nav { display:flex; align-items:center; justify-content:space-between; padding:0 0 1.35rem; }
        .brand { display:flex; align-items:center; gap:9px; font-size:18px; font-weight:800; letter-spacing:0; }
        .brand-mark { width:20px; height:20px; border:2px solid var(--ink); border-radius:4px; display:inline-block; box-sizing:border-box; position:relative; }
        .brand-mark:after { content:""; position:absolute; width:7px; height:14px; background:#fff; border-left:2px solid var(--ink); border-right:2px solid var(--ink); left:5px; top:1px; }
        .nav-links { color:#4f4f4f; font-size:12px; display:flex; gap:28px; align-items:center; }
        .nav-pill { background:var(--ink); color:#fff; border-radius:7px; padding:10px 15px; font-weight:600; }
        .hero-copy { padding:62px 0 48px; min-height:365px; display:flex; flex-direction:column; justify-content:center; }
        .preview-panel { height:360px; border:1px solid var(--line); border-radius:10px; background:#fff; position:relative; overflow:hidden; }
        .preview-empty { display:flex; height:100%; align-items:center; justify-content:center; color:#9a9a9a; font-size:12px; }
        .eyebrow { font-family:"DM Mono",monospace; font-size:11px; color:#777; letter-spacing:.08em; text-transform:uppercase; margin-bottom:12px; }
        .hero-copy h1 { font-size:58px; line-height:1; letter-spacing:0; margin:0 0 18px; font-weight:800; }
        .hero-copy h2 { font-size:28px; line-height:1.35; margin:0 0 18px; font-weight:700; }
        .hero-copy p { color:var(--muted); font-size:14px; line-height:1.85; max-width:480px; margin:0; }
        .hero-visual { position:relative; min-height:290px; }
        .image-stack { position:absolute; inset:15px 10px 0 55px; transform:rotate(-7deg); background:#f4f0eb; border:8px solid white; border-radius:12px; box-shadow:0 17px 28px rgba(30,25,20,.14); overflow:hidden; }
        .image-stack img { width:100%; height:100%; object-fit:cover; }
        .intent-note { position:absolute; top:0; left:0; z-index:2; background:#fff; border:1px solid var(--line); box-shadow:0 10px 20px rgba(30,25,20,.08); border-radius:10px; padding:15px 18px; font-size:12px; line-height:1.7; }
        .intent-note strong { display:block; font-size:13px; }
        .intent-note.bottom { left:auto; right:0; top:auto; bottom:-5px; }
        .primary-row { display:flex; gap:12px; margin:10px 0 22px; }
        .primary-row button { border-radius:8px!important; font-weight:700!important; min-height:42px!important; }
        .metric-row { display:flex; flex-wrap:wrap; gap:20px; color:#686868; font-size:12px; }
        .metric-row span:before { content:"✓"; color:#5d9567; border:1px solid #a7c6aa; border-radius:100%; width:15px; height:15px; display:inline-flex; align-items:center; justify-content:center; margin-right:7px; font-size:10px; }
        .value-strip { margin:28px 0 54px; display:grid; grid-template-columns:repeat(3,1fr); padding:27px 15px; }
        .value { text-align:center; padding:6px 18px; border-right:1px solid var(--line); }
        .value:last-child { border:0; }
        .value .icon { font-size:24px; display:block; margin-bottom:10px; }
        .value h3 { margin:0 0 6px; font-size:16px; }.value p{margin:0;color:var(--muted);font-size:12px;}
        .section-title { margin:0 0 3px; font-size:25px; font-weight:800; }.section-kicker { color:var(--muted); font-size:13px; margin:0 0 20px; }
        .stTextArea textarea { border-radius:8px!important; border-color:var(--line)!important; background:#faf9f7!important; min-height:86px!important; font-family:"Noto Sans SC",sans-serif!important; }
        .check-card { display:flex; align-items:center; justify-content:space-between; border:1px solid var(--line); border-radius:7px; padding:11px 13px; margin:8px 0; font-size:12px; background:#fff; }.check-card .ok{color:var(--green);font-size:11px;font-weight:700;}
        .result-box { background:#faf9f7; border:1px solid var(--line); padding:10px; border-radius:8px; }.result-box img { border-radius:5px; width:100%; max-height:370px; object-fit:cover; }.result-caption{color:#686868;font-size:12px;line-height:1.65;margin:11px 4px 2px;}
        .tags { display:flex; gap:7px; flex-wrap:wrap; margin:10px 4px 2px; }.tag { border:1px solid #dcd9d5; border-radius:14px; padding:3px 8px; font-size:10px; color:#666; }
        .memory-wrap { background:#fff; border:1px solid var(--line); border-radius:10px; padding:30px; margin-bottom:52px; }.memory-note{font-size:13px;color:var(--muted);margin:0 0 24px;}.memory-card{border:1px solid var(--line);border-radius:8px;padding:16px;min-height:164px;background:#fff;}.memory-card h4{font-size:13px;margin:0 0 13px;}.memory-card dl{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px;}.memory-card dt{color:#8a8a8a;}.memory-card dd{margin:0;font-weight:600;}.memory-link{display:block;margin-top:13px;font-size:11px;color:#5373a4;font-weight:700;}
        .process { padding:3px 8px 48px; }.step { text-align:center; position:relative; }.step:not(:last-child):after { content:"→"; position:absolute; right:-9px; top:22px; color:#c2c2c2; font-size:25px; }.step-icon{height:52px;width:52px;border-radius:50%;background:#f4f2ee;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;font-size:22px;}.step h4{margin:0 0 5px;font-size:14px;}.step p{margin:0;color:var(--muted);font-size:11px;line-height:1.6;}
        .footer { border-top:1px solid var(--line); padding:21px 2px 28px; color:#8b8b8b; font-size:11px; display:flex; justify-content:space-between; }
        .workspace-shell { min-height:calc(100vh - 5rem); }
        .workspace-nav { padding:8px 20px 22px 5px; border-right:1px solid #e7e7e4; min-height:calc(100vh - 5rem); }
        .workspace-brand { display:flex; gap:9px; align-items:center; font-size:18px; font-weight:800; margin:0 0 34px; }
        .workspace-label { color:#7d7d7d; font-size:12px; font-weight:700; margin:23px 0 9px; }
        .nav-item { border-radius:9px; padding:12px 13px; font-size:13px; font-weight:600; color:#444; margin:5px 0; }
        .nav-item.active { color:#39854c; background:#f1f7f1; border:1px solid #e2eee3; }
        .status-card { border:1px solid #e7e6e3; border-radius:9px; padding:13px; font-size:12px; margin-top:290px; }.status-card b { color:#42a55a; display:block; margin-top:7px; font-size:11px; }
        .workspace-head { display:flex; justify-content:space-between; align-items:center; height:46px; border-bottom:1px solid #e7e7e4; margin-bottom:18px; }.workspace-head h3 { font-size:14px; margin:0; }.workspace-head p { color:#888; font-size:12px; margin:3px 0 0; }
        .chat-user { margin:16px max(10%, 80px) 28px auto; max-width:350px; }.chat-user label { color:#777; font-size:11px; display:block; margin:0 0 6px; }.chat-user p { margin:0; background:#f1f1f1; border-radius:10px; padding:10px 13px; font-size:13px; line-height:1.6; }
        .chat-assistant { margin:8px auto 38px max(10%, 80px); max-width:420px; }.chat-assistant .assistant-name { font-weight:700; font-size:12px; margin-bottom:5px; }.chat-assistant .assistant-copy { color:#6f6f6f; font-size:12px; line-height:1.55; margin-bottom:10px; }
        .generated-card { width:100%; border:1px solid #e5e3df; border-radius:8px; background:#f6f7f5; display:flex; align-items:center; justify-content:center; color:#9a9a9a; font-size:12px; overflow:hidden; }.generated-card img { width:100%; height:100%; object-fit:cover; }
        .workspace-hint { text-align:center; color:#9a9a9a; font-size:12px; padding:90px 0; }
        [data-testid="stChatInput"] { max-width:760px; margin:0 auto 12px; }.stChatInput { border-radius:28px!important; box-shadow:0 7px 20px rgba(0,0,0,.08)!important; border:1px solid #e5e4e1!important; }
        .stButton>button { box-shadow:none!important; }.stButton>button[kind="primary"] { background:#171717!important; border-color:#171717!important; }
        @media(max-width:760px) { .block-container{padding:1rem 1rem 0}.nav-links{display:none}.hero-copy{padding:30px 0;min-height:unset}.hero-copy h1{font-size:41px}.hero-copy h2{font-size:22px}.preview-panel{height:245px}.value-strip{grid-template-columns:1fr;padding:12px}.value{border-right:0;border-bottom:1px solid var(--line);padding:16px}.value:last-child{border-bottom:0}.memory-wrap{padding:22px}.footer{display:block;line-height:2}.step:not(:last-child):after{display:none} }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_nav() -> None:
    st.markdown('<div class="top-nav"><div class="brand"><span class="brand-mark"></span>Mem2Image</div></div>', unsafe_allow_html=True)


def _render_hero() -> None:
    left, right = st.columns([1.08, 0.92], gap="large")
    with left:
        st.markdown('<div class="hero-copy"><div class="eyebrow">Visual Intent Memory / Research Prototype</div><h1>Mem2Image</h1><h2>让多轮对话更懂你的视觉意图</h2><p>Mem2Image 通过 Visual Intent Memory 记住你在对话中的偏好、对象与需求，让每一次生成都更贴合你的期待。</p></div>', unsafe_allow_html=True)
        a, b, _ = st.columns([1, 1, 2])
        with a:
            if st.button("开始创作  →", type="primary", use_container_width=True):
                st.session_state.page = "workspace"
                st.rerun()
        with b:
            if st.button("打开工作台", use_container_width=True):
                st.session_state.page = "workspace"
                st.rerun()
        with _:
            if st.button("管理员登录", use_container_width=True, key="hero_admin"):
                st.session_state.page = "admin"
                st.rerun()
        st.markdown('<div class="metric-row"><span>更懂语境</span><span>更高一致性</span><span>更可控生成</span></div>', unsafe_allow_html=True)
    with right:
        image = _preview_image()
        image_src = _file_as_data_uri(image) if image else ""
        visual = f'<div class="image-stack"><img src="{image_src}"/></div>' if image_src else '<div class="preview-empty">首轮生成后将在这里展示视觉结果</div>'
        st.markdown('<div class="preview-panel"><div class="hero-visual"><div class="intent-note"><strong>记住你的偏好</strong>造型比例、视角、风格...</div>' + visual + '<div class="intent-note bottom"><strong>持续优化输出</strong>追踪细节，延用越顺手</div></div></div>', unsafe_allow_html=True)


def _render_value_strip() -> None:
    st.markdown(
        '<div class="value-strip"><div class="value"><span class="icon">◌</span><h3>懂你想要的</h3><p>理解上下文，捕捉关键意图</p></div>'
        '<div class="value"><span class="icon">⌘</span><h3>保持高度一致</h3><p>风格、主体、构图始终如一</p></div>'
        '<div class="value"><span class="icon">ϟ</span><h3>高效又可控</h3><p>少试错，快速得到理想结果</p></div></div>',
        unsafe_allow_html=True,
    )


def _render_workspace(settings: Settings) -> None:
    sidebar, content = st.columns([1.1, 4.6], gap="medium")
    with sidebar:
        st.markdown('<aside class="workspace-nav"><div class="workspace-brand"><span class="brand-mark"></span>Mem2Image</div><div class="workspace-label">工作区</div><div class="nav-item active">⌂　我的工作台</div><div class="nav-item">▱　我的项目</div><div class="status-card">状态信息<b>● 已连接</b><span style="color:#8a8a8a;font-size:11px">服务运行正常</span></div></aside>', unsafe_allow_html=True)
        if st.button("管理员入口", use_container_width=True, key="workspace_admin"):
            st.session_state.page = "admin"
            st.rerun()
        if st.button("← 返回主页", use_container_width=True, key="back_home"):
            st.session_state.page = "home"
            st.rerun()
    with content:
        st.markdown('<header class="workspace-head"><div><h3>我的工作台　⌄</h3><p>使用自然语言持续编辑你的画面</p></div></header>', unsafe_allow_html=True)
        history = st.session_state.results
        if not history:
            st.markdown('<div class="workspace-hint">从底部输入框开始描述你想生成或调整的画面</div>', unsafe_allow_html=True)
        for result in history:
            _render_chat_turn(result)
        prompt = st.chat_input("继续描述你想编辑的画面…")
        if prompt:
            _run_turn(settings, prompt.strip())
        if st.session_state.last_error:
            st.error(st.session_state.last_error)


def _render_chat_turn(result: Dict[str, Any]) -> None:
    instruction = html.escape(result.get("instruction", ""))
    st.markdown(f'<div class="chat-user"><label>你</label><p>{instruction}</p></div>', unsafe_allow_html=True)
    image = Path(result.get("image_path", ""))
    image_size = result.get("image_size", "")
    aspect_ratio = _image_aspect_ratio(image_size)
    image_html = ""
    if _is_displayable_image(image):
        image_src = _file_as_data_uri(image)
        image_html = f'<div class="generated-card" style="aspect-ratio:{aspect_ratio}"><img src="{image_src}" alt="生成结果" /></div>'
    else:
        image_html = f'<div class="generated-card" style="aspect-ratio:{aspect_ratio}">生成结果将在这里显示</div>'
    st.markdown('<div class="chat-assistant"><div class="assistant-name">◫　Mem2Image</div><div class="assistant-copy">已完成本轮调整，并保留此前的视觉意图与主体设定。</div>' + image_html + '</div>', unsafe_allow_html=True)


def _render_dashboard() -> None:
    top_left, top_right = st.columns([4, 1])
    with top_left:
        st.markdown('<div class="eyebrow">Evaluation Dashboard</div><h2 style="margin:0 0 6px;font-size:28px">实验看板</h2><p style="color:#757575;font-size:13px;margin:0 0 18px">查看 SQLite 中沉淀的 benchmark、run、turn、checklist 和 bad case 数据。</p>', unsafe_allow_html=True)
    with top_right:
        if st.button("退出看板", use_container_width=True, key="dashboard_home"):
            st.session_state.page = "home"
            st.rerun()

    run_ids = list_benchmark_run_ids()
    options = ["全部数据"] + run_ids
    selected = st.selectbox("Benchmark run", options=options, index=0)
    benchmark_run_id = "" if selected == "全部数据" else selected

    totals = dashboard_totals(benchmark_run_id=benchmark_run_id)
    metric_cols = st.columns(7)
    metric_cols[0].metric("Methods", totals["method_count"])
    metric_cols[1].metric("Cases", totals["case_count"])
    metric_cols[2].metric("Turns", totals["turn_count"])
    metric_cols[3].metric("Avg Score", _fmt_metric(totals["avg_checklist_score"]))
    metric_cols[4].metric("History", _fmt_metric(totals["history_retention_rate"]))
    metric_cols[5].metric("Current", _fmt_metric(totals["current_turn_success_rate"]))
    metric_cols[6].metric("Failed", totals["failed_item_count"])

    method_rows = summarize_methods(benchmark_run_id=benchmark_run_id)
    drift_rows = summarize_drift_types(benchmark_run_id=benchmark_run_id)
    badcase_matrix_rows = list_turn_badcase_matrix(benchmark_run_id=benchmark_run_id)
    turn_rows = list_turn_metrics(benchmark_run_id=benchmark_run_id)
    failed_rows = list_failed_items(benchmark_run_id=benchmark_run_id)

    tabs = st.tabs(["逐轮 Badcase", "Method 对比", "Drift 类型", "Turn 明细", "Bad Cases", "原始 Runs"])
    with tabs[0]:
        st.caption("每一轮一行。status=BAD 表示该轮至少一个 checklist item 未通过；failed_items 显示失败项、失败类型和来源。")
        filtered_matrix = _filter_badcase_matrix(badcase_matrix_rows)
        _dataframe_or_empty(filtered_matrix, "暂无逐轮评测数据。")
        bad_rows = [row for row in filtered_matrix if row.get("status") == "BAD"]
        if bad_rows:
            st.subheader("当前筛选下的 badcase")
            for row in bad_rows:
                with st.expander(
                    f"{row.get('method')} / {row.get('case_id')} / Turn {row.get('turn_index')} "
                    f"- score {row.get('checklist_score')}"
                ):
                    st.write(row.get("instruction", ""))
                    st.json(
                        {
                            "failed_item_count": row.get("failed_item_count"),
                            "critical_failed_count": row.get("critical_failed_count"),
                            "history_retention": row.get("history_retention"),
                            "current_success": row.get("current_success"),
                            "failed_items": row.get("failed_items"),
                            "failed_reasons": row.get("failed_reasons"),
                            "image_path": row.get("image_path"),
                        }
                    )
    with tabs[1]:
        st.caption("方法级聚合。History/Current 使用 v2-style per-turn aggregation。")
        _dataframe_or_empty(method_rows, "暂无 method 聚合数据。")
    with tabs[2]:
        st.caption("按 drift_type 汇总失败和通过率。")
        _dataframe_or_empty(drift_rows, "暂无 drift type 数据。")
    with tabs[3]:
        st.caption("每一轮的输入、分数、失败数量和图像路径。")
        _dataframe_or_empty(turn_rows, "暂无 turn 数据。")
    with tabs[4]:
        st.caption("所有未通过 checklist item，可用于 bad case 分析。")
        _dataframe_or_empty(failed_rows, "当前筛选下没有失败项。")
        if failed_rows:
            first = failed_rows[0]
            st.subheader("最新失败项")
            st.write(f"**{first.get('case_id') or '-'} / {first.get('method') or '-'} / Turn {first.get('turn_index')}**")
            st.write(first.get("question", ""))
            st.json({k: first.get(k) for k in ("target", "answer", "drift_type", "source", "critical", "reason")})
    with tabs[5]:
        st.caption(f"SQLite database: `{database.DEFAULT_DB_PATH}`")
        _dataframe_or_empty(database.list_runs(), "暂无 run 数据。")


def _render_admin_gate() -> None:
    if st.session_state.admin_authenticated:
        _render_dashboard()
        return

    left, middle, right = st.columns([1, 1.35, 1])
    with middle:
        st.markdown('<div class="eyebrow">Admin Only</div><h2 style="margin:0 0 8px;font-size:28px">管理员登录</h2><p style="color:#757575;font-size:13px;margin:0 0 20px">实验看板包含 run、评测、失败项和调试数据，仅管理员可见。</p>', unsafe_allow_html=True)
        password = st.text_input("管理员口令", type="password", key="admin_password_input")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("进入实验看板", type="primary", use_container_width=True, key="admin_login"):
                if _check_admin_password(password):
                    st.session_state.admin_authenticated = True
                    st.session_state.admin_error = ""
                    st.rerun()
                else:
                    st.session_state.admin_error = "管理员口令不正确。"
        with col2:
            if st.button("返回主页", use_container_width=True, key="admin_back_home"):
                st.session_state.page = "home"
                st.session_state.admin_error = ""
                st.rerun()
        if st.session_state.admin_error:
            st.error(st.session_state.admin_error)
        if not os.getenv("MEM2IMAGE_ADMIN_PASSWORD"):
            st.caption("本地开发提示：未设置 MEM2IMAGE_ADMIN_PASSWORD，当前使用默认口令 admin。部署前请在环境变量中设置正式管理员口令。")


def _check_admin_password(password: str) -> bool:
    expected = os.getenv("MEM2IMAGE_ADMIN_PASSWORD", "admin")
    return bool(password) and password == expected


def _render_memory_section() -> None:
    memory = st.session_state.memory
    cards = [
        ("主体设定", [("车型类别", memory.get("subject", {}).get("category", "跑车")), ("品牌", memory.get("subject", {}).get("brand", "通用")), ("颜色", memory.get("subject", {}).get("color", "银白色"))]),
        ("风格设定", [("风格", memory.get("style", {}).get("style", "真实摄影")), ("光线", memory.get("style", {}).get("lighting", "夜景 / 柔光")), ("质感", memory.get("style", {}).get("quality", "高细节"))]),
        ("构图设定", [("视角", memory.get("composition", {}).get("view", "低角度")), ("景别", memory.get("composition", {}).get("shot", "近景")), ("画幅比例", memory.get("composition", {}).get("aspect_ratio", "16:9"))]),
        ("偏好设定", [("不喜欢", "过度 HDR"), ("不喜欢", "卡通渲染"), ("重点关注", "灯光氛围")]),
    ]
    st.markdown('<div class="memory-wrap"><h3 class="section-title">Visual Intent Memory</h3><p class="memory-note">记住你的设定，自动应用到每一次生成</p></div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    for col, (title, items) in zip(cols, cards):
        with col:
            body = "".join(f"<dt>{key}</dt><dd>{value}</dd>" for key, value in items)
            st.markdown(f'<div class="memory-card"><h4>{title}</h4><dl>{body}</dl><span class="memory-link">查看全部 ›</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="margin:20px 0 52px;background:#fff;border:1px solid #e9e6e1;border-radius:10px;padding:13px;text-align:center;color:#6a625b;font-size:12px">Mem2Image 会持续学习并优化你的偏好，让每一次生成都更贴心。</div>', unsafe_allow_html=True)


def _render_process() -> None:
    st.markdown('<h3 class="section-title">工作流程</h3><p class="section-kicker">简单四步，我帮你理想画面</p>', unsafe_allow_html=True)
    labels = [("◌", "输入需求", "用自然语言描述你想要的画面"), ("◎", "理解意图", "提取关键信息与偏好"), ("▣", "生成画面", "结合记忆生成高质量结果"), ("✓", "持续优化", "反馈调整，越用越懂你")]
    cols = st.columns(4)
    for col, (icon, title, text) in zip(cols, labels):
        with col:
            st.markdown(f'<div class="step"><div class="step-icon">{icon}</div><h4>{title}</h4><p>{text}</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="process"></div>', unsafe_allow_html=True)


def _render_footer() -> None:
    st.markdown('<footer class="footer"><span><b>◫ Mem2Image</b><br>让多轮对话更懂你的视觉意图</span><span>Research Prototype · 2026</span></footer>', unsafe_allow_html=True)


def _dataframe_or_empty(rows: list[Dict[str, Any]], empty_text: str) -> None:
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info(empty_text)


def _filter_badcase_matrix(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    if not rows:
        return rows

    filter_cols = st.columns([1, 1, 1])
    methods = ["全部方法"] + sorted({str(row.get("method")) for row in rows if row.get("method")})
    cases = ["全部 case"] + sorted({str(row.get("case_id")) for row in rows if row.get("case_id")})
    statuses = ["全部状态", "BAD", "OK"]

    with filter_cols[0]:
        selected_method = st.selectbox("Method", methods, index=0)
    with filter_cols[1]:
        selected_case = st.selectbox("Case", cases, index=0)
    with filter_cols[2]:
        selected_status = st.selectbox("Status", statuses, index=0)

    result = rows
    if selected_method != "全部方法":
        result = [row for row in result if row.get("method") == selected_method]
    if selected_case != "全部 case":
        result = [row for row in result if row.get("case_id") == selected_case]
    if selected_status != "全部状态":
        result = [row for row in result if row.get("status") == selected_status]
    return result


def _fmt_metric(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "0.000"


def _run_turn(settings: Settings, instruction: str) -> None:
    if not instruction:
        st.session_state.last_error = "请输入本轮画面需求。"
        return
    if not settings.api_key:
        st.session_state.last_error = "尚未配置 SiliconFlow API Key。请在左侧设置后运行真实生成。"
        return
    st.session_state.last_error = ""
    turn_index = len(st.session_state.results) + 1
    orchestrator = Mem2ImageOrchestrator(settings=settings, run_id=st.session_state.run_id)
    with st.spinner(f"正在生成第 {turn_index} 轮画面，并检查记忆一致性..."):
        try:
            result = orchestrator.run_turn(instruction=instruction, memory=st.session_state.memory, turn_index=turn_index)
        except Exception as exc:
            st.session_state.last_error = str(exc)
            return
    st.session_state.memory = result.memory
    result_state = _result_to_state(result)
    result_state["image_size"] = settings.image_size
    st.session_state.results.append(result_state)
    st.rerun()


def _preview_image() -> Path | None:
    if st.session_state.results:
        latest = Path(st.session_state.results[-1].get("image_path", ""))
        if _is_displayable_image(latest):
            return latest
    if _is_displayable_image(HERO_IMAGE_PATH):
        return HERO_IMAGE_PATH
    return None


def _file_as_data_uri(path: Path) -> str:
    import base64

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _is_displayable_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 64:
        return False
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def _image_aspect_ratio(image_size: str) -> str:
    parts = image_size.lower().replace(" ", "").split("x")
    if len(parts) != 2:
        return "1 / 1"
    try:
        width, height = (int(part) for part in parts)
    except ValueError:
        return "1 / 1"
    if width <= 0 or height <= 0:
        return "1 / 1"
    return f"{width} / {height}"


def _result_to_state(result: TurnResult) -> Dict[str, Any]:
    return {
        "turn_index": result.turn_index,
        "instruction": result.instruction,
        "delta": result.delta,
        "memory": result.memory,
        "prompt": {"positive": result.prompt.positive, "negative": result.prompt.negative},
        "checklist": result.checklist,
        "evaluation": result.evaluation,
        "image_path": str(result.image_path),
        "run_dir": str(result.run_dir),
    }


if __name__ == "__main__":
    main()
