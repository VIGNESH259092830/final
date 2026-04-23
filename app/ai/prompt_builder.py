def build_interview_prompt(session_data: dict, current_question: str, history: list = None) -> str:
    """Build interview-aware prompt using session data and history"""
    
    # Extract session data
    company = session_data.get('company', 'Unknown Company')
    job_desc = session_data.get('job_description', 'No job description')
    resume = session_data.get('resume_text', 'No resume provided')
    extra_context = session_data.get('extra_context', 'No extra context')
    
    # Build base prompt
    prompt = f"""You are an AI interview assistant helping a candidate prepare for a job interview.

IMPORTANT CONTEXT:
- Company: {company}
- Job Description: {job_desc}
- Candidate Resume: {resume}
- Additional Instructions: {extra_context}

INTERVIEW RULES:
1. Provide professional, interview-style answers
2. Tailor responses to match the company culture and job requirements
3. Reference the candidate's resume when relevant
4. Use bullet points for clarity
5. Include code examples when discussing technical topics
6. Keep answers concise but comprehensive

IMPORTANT FORMATTING RULES FOR CODE:
1. When providing code, wrap it in triple backticks with language specification
2. Format: ```python\n# your code here\n```
3. Supported languages: python, javascript, java, cpp, c, html, css, sql, bash
4. Include comments in code for clarity
5. For HTML/CSS questions, provide complete, working examples

CONVERSATION HISTORY:
"""
    
    # Add conversation history
    if history:
        for item in history:
            role = "Interviewer" if item["role"] == "question" else "Candidate"
            prompt += f"\n{role}: {item['content']}"
    else:
        prompt += "\nNo previous conversation history."
    
    # Add current question
    prompt += f"""

CURRENT INTERVIEW QUESTION:
"{current_question}"

Please provide a well-structured interview answer that:
1. Directly addresses the question
2. Includes relevant code examples if technical
3. Incorporates experience from the resume
4. Aligns with the job requirements
5. Shows practical implementation

ANSWER:
"""
    
    return prompt