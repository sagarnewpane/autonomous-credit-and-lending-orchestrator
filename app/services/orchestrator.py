from langgraph.graph import StateGraph, END
from app.models.state import AgentState
from app.agents.parser_agent import parser_node  # Your other agent
from app.agents.income_agent import analyze 

workflow = StateGraph(AgentState)

# Add your agents as nodes
workflow.add_node("parser", parser_node)
workflow.add_node("income_analyzer", analyze)

# Connect them: Parser output flows into Income input
workflow.set_entry_point("parser")
workflow.add_edge("parser", "income_analyzer")
workflow.add_edge("income_analyzer", END)

app = workflow.compile()

# @app.post("/apply-loan")
# async def apply(data: LoanRequest):
#     # Initial "Briefcase" contents
#     initial_state = {
#         "file_paths": ["uploads/lal_purja.png"],
#         "raw_transactions": db.get_user_transactions(data.user_id),
#         "errors": []
#     }
    
#     # Run the whole pipeline
#     final_result = await credit_engine.ainvoke(initial_state)