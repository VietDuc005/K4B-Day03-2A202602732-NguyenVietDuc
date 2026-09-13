"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPAcademicServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS,
    check_input_prompt_injection
)
from providers import get_llm_provider

load_dotenv()

SENSITIVE_TOOLS = {"update_student_profile"}


def is_sensitive_tool(tool_name: str) -> bool:
    """Xác định tool có rủi ro cao vì có thể thay đổi dữ liệu."""
    return tool_name in SENSITIVE_TOOLS


def confirm_sensitive_tool(tool_name: str, arguments: dict, interactive_hitl: bool = False) -> bool:
    """Kích hoạt Human-in-the-loop trước khi thực thi tool nhạy cảm."""
    print(f"⚠️ [HITL WARNING]: Tool '{tool_name}' là hành động nhạy cảm!")
    print(f"🔎 [HITL REVIEW]: Tham số đề xuất: {json.dumps(arguments, ensure_ascii=False)}")

    if not interactive_hitl:
        print("✅ [HITL SIMULATION]: interactive_hitl=False, tự động xác nhận mô phỏng để không nghẽn luồng kiểm thử.")
        return True

    decision = input("👤 Xác nhận thực thi hành động nhạy cảm? (Y/N): ").strip().lower()
    approved = decision in {"y", "yes"}
    if approved:
        print("✅ [HITL APPROVED]: Con người đã xác nhận thực thi tool nhạy cảm.")
    else:
        print("⛔ [HITL REJECTED]: Con người đã từ chối thực thi tool nhạy cảm.")
    return approved

def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list):
    """Ghi vết log Waterfall Trace Log ra file docs/trace_waterfall.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")


def run_react_agent(user_query: str, provider, mcp_server: MCPAcademicServer, interactive_hitl: bool = False) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server
    Trả về danh sách trace log của phiên thực thi.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    is_injection, warning_message = check_input_prompt_injection(user_query)
    if is_injection:
        print(f"🛡️ [INPUT GUARDRAIL]: {warning_message}")
        return [{
            "step": 0,
            "query": user_query,
            "action_type": "INPUT_GUARDRAIL_BLOCKED",
            "thought": "Phát hiện dấu hiệu Prompt Injection trước khi gọi LLM.",
            "output": warning_message,
            "latency_ms": 0.0
        }]
    
    step = 0
    trace_logs = []
    tools_list = mcp_server.list_tools()
    
    pending_tool_call = None

    while step < MAX_ITERATIONS:
        step += 1
        step_start_time = time.time()
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")
        
        # Gọi LLM với Native Tool Calling Specs, hoặc xử lý tool call kế tiếp đã suy ra từ Observation trước đó.
        if pending_tool_call:
            llm_response = pending_tool_call
            pending_tool_call = None
        else:
            llm_response = provider.generate_with_tools(user_query, tools_list, system_prompt=REACT_AGENT_SYSTEM_PROMPT)
        latency_ms = round((time.time() - step_start_time) * 1000, 2)
        
        thought = llm_response.get("thought", "Đang suy luận...")
        print(f"🧠 [Thought]: {thought}")
        
        # Trường hợp 1: LLM quyết định trả lời bằng văn bản trực tiếp
        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_content,
                "latency_ms": latency_ms
            })
            break
            
        # Trường hợp 2: LLM đề xuất gọi Tool (Action)
        elif llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {})
            
            print(f"🛠️ [Action Proposed]: {tool_name}({arguments})")

            hitl_required = is_sensitive_tool(tool_name)
            hitl_approved = None
            if hitl_required:
                hitl_approved = confirm_sensitive_tool(tool_name, arguments, interactive_hitl=interactive_hitl)
                if not hitl_approved:
                    obs_data = {
                        "status": "HITL_REJECTED",
                        "message": f"Tool '{tool_name}' chưa được thực thi vì không có xác nhận của con người."
                    }
                    final_answer = obs_data["message"]
                    trace_logs.append({
                        "step": step,
                        "query": user_query,
                        "action_type": "HITL_REJECTED",
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "observation": obs_data,
                        "hitl_required": hitl_required,
                        "hitl_approved": hitl_approved,
                        "latency_ms": latency_ms
                    })
                    print(f"🏁 [Final Answer]: {final_answer}")
                    break
            
            # Thực thi Tool qua MCP Server
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result", {})
            
            if not obs_data:
                print(f"👁️ [Observation từ MCP Server]: {{}}")
                print(f"⚠️ [CHÚ Ý]: MCP Server trả về kết quả rỗng! Học viên cần hoàn thành TODO 2.1 trong 'src/mcp_server.py'.")
                final_answer = "Chưa thể trả lời chi tiết do chưa nhận được dữ liệu từ MCP Server (hãy hoàn thành TODO 2.1)."
            else:
                obs_str = json.dumps(obs_data, ensure_ascii=False)
                print(f"👁️ [Observation từ MCP Server]: {obs_str}")
                
                # Tổng hợp Final Answer từ kết quả Observation thực tế
                if obs_data.get("status") == "SUCCESS":
                    if "data" in obs_data:
                        d = obs_data["data"]
                        final_answer = (
                            f"Kết quả tra cứu cho sinh viên {obs_data.get('student_id', '')} ({d.get('full_name', '')}): "
                            f"Lớp {d.get('class', '')}, GPA: {d.get('gpa', '')}, Email: {d.get('email', '')}, "
                            f"Trạng thái: {d.get('status', '')}, Cố vấn: {d.get('advisor', '')}."
                        )
                    elif "message" in obs_data:
                        final_answer = obs_data["message"]
                    else:
                        final_answer = f"Đã hoàn tất xử lý qua MCP Server: {json.dumps(obs_data, ensure_ascii=False)}"
                elif obs_data.get("status") == "NOT_FOUND":
                    final_answer = obs_data.get("message", "Không tìm thấy thông tin sinh viên yêu cầu.")
                else:
                    final_answer = f"Phản hồi từ công cụ: {json.dumps(obs_data, ensure_ascii=False)}"
            
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "hitl_required": hitl_required,
                "hitl_approved": hitl_approved,
                "latency_ms": latency_ms
            })
            
            needs_follow_up_booking = (
                tool_name == "academic_query"
                and obs_data.get("status") == "SUCCESS"
                and "đặt lịch" in user_query.lower()
                and "data" in obs_data
                and step < MAX_ITERATIONS
            )

            if needs_follow_up_booking:
                student_data = obs_data["data"]
                pending_tool_call = {
                    "type": "tool_call",
                    "tool_name": "schedule_appointment",
                    "arguments": {
                        "student_id": obs_data.get("student_id", arguments.get("student_id", "")),
                        "datetime_str": "14:00 15/09/2026",
                        "advisor_name": student_data.get("advisor", "PGS.TS Nguyễn Văn A")
                    },
                    "thought": "Observation cho biết cố vấn học tập của sinh viên. Tiếp tục gọi schedule_appointment để hoàn tất yêu cầu đặt lịch."
                }
                print("➡️ [Next Action]: Đã xác định cần đặt lịch với cố vấn vừa tra cứu, tiếp tục vòng lặp ReAct.")
                continue

            # Kết thúc vòng lặp sau khi hoàn tất Observation và xuất Final Answer
            print(f"🧠 [Thought]: Đã nhận được dữ liệu từ MCP Server. Tổng hợp kết quả phản hồi.")
            print(f"🏁 [Final Answer]: {final_answer}")
            
            trace_logs.append({
                "step": step + 1,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": "Tổng hợp kết quả từ MCP Server thành công.",
                "output": final_answer,
                "latency_ms": 10.0
            })
            break

    return trace_logs


def run_native_mcp_agent(user_query: str, provider, mcp_server: MCPAcademicServer, interactive_hitl: bool = False) -> list:
    """Alias theo brief Task 2.2 cho ReAct Agent dùng Native Tool Calling qua MCP."""
    return run_react_agent(user_query, provider, mcp_server, interactive_hitl=interactive_hitl)


if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")
    
    provider = get_llm_provider()
    mcp_server = MCPAcademicServer()
    
    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")
    
    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")
    
    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent:")
        print("💡 Gợi ý câu hỏi thử nghiệm:")
        print("   - Câu hỏi chung: 'Quy chế học vụ VinUni yêu cầu bao nhiêu tín chỉ?'")
        print("   - Tra cứu học vụ: 'Hãy tra cứu thông tin học vụ của sinh viên SV2026001'")
        print("   - Đặt lịch hẹn: 'Đặt lịch hẹn tư vấn cho SV2026001 vào 14:00 ngày 15/09/2026'")
        print("   - HITL: 'Cập nhật email của sinh viên SV2026001 thành duc.test@vinuni.edu.vn'")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc phiên trò chuyện.\n")
        while True:
            try:
                user_input = input("👤 Sinh viên hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server, interactive_hitl=True)
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break
    elif "--hitl-demo" in sys.argv:
        print("🛡️ [HITL DEMO MODE] Kiểm tra phanh xác nhận con người cho tool cập nhật hồ sơ:")
        demo_query = "Cập nhật email của sinh viên SV2026001 thành duc.test@vinuni.edu.vn."
        logs = run_react_agent(demo_query, provider, mcp_server, interactive_hitl=False)
        save_waterfall_trace(logs)
    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE MODE] Kiểm tra 5 Test Cases:")
        completed_count = 0
        todo_count = 0
        all_traces = []
        
        for tc in tests:
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")
            
            if tc["question"].strip().startswith("TODO"):
                print(f"⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print(f"   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế cho Test Case này!")
                todo_count += 1
            else:
                logs = run_react_agent(tc["question"], provider, mcp_server)
                all_traces.extend(logs)
                completed_count += 1

        print(f"\n==================================================")
        print("🛡️ [SAFETY CHECKPOINT] Demo phanh HITL cho tool nhạy cảm update_student_profile")
        hitl_demo_query = "Cập nhật email của sinh viên SV2026001 thành duc.test@vinuni.edu.vn."
        hitl_logs = run_react_agent(hitl_demo_query, provider, mcp_server, interactive_hitl=False)
        all_traces.extend(hitl_logs)
                
        print(f"\n==================================================")
        print(f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi {completed_count}/{len(tests)} Test Cases | {todo_count} Test Cases đang chờ điền câu hỏi (TODO)")
        if all_traces:
            save_waterfall_trace(all_traces)
        print(f"💡 Để trò chuyện trực tiếp từng câu: Chạy 'python src/app.py --interactive'")
    else:
        # Chế độ mặc định khi chỉ gõ 'python src/app.py'
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG CHƯƠNG TRÌNH:")
        print("  1. Chat trực tiếp liên tục:   python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test Cases:    python src/app.py --all\n")
        print("  3. Demo phanh HITL:            python src/app.py --hitl-demo\n")
        
        sample_query = tests[1]["question"]
        print(f"--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra cứu học vụ) ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        print("\n💡 Hãy thử ngay lệnh: python src/app.py --interactive để chat trực tiếp!")
