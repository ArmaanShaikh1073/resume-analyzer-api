# app/services/jd_matcher.py
import google.generativeai as genai
from app.config import settings
import json
import re
from typing import Dict, List, Any

def setup_gemini():
    """
    Configure the Gemini API client
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    print("Gemini API configured for JD matcher")

def compare_resume_jd(resume_text: str, jd_text: str) -> dict:
    """
    Compare resume text against job description using Gemini API
    Returns a structured analysis with match score, skills, and recommendations
    """
    print(f"Starting comparison of resume ({len(resume_text)} chars) with job description ({len(jd_text)} chars)")
    
    # Default error response
    error_response = {
        "error": None,
        "score": 0,
        "matching_skills": [],
        "missing_skills": [],
        "recommendations": [],
        "category_scores": {
            "Technical Skills": 0,
            "Experience": 0,
            "Education": 0,
            "Soft Skills": 0,
            "Industry Knowledge": 0
        }
    }
    
    # Check if API key is set
    if not settings.GEMINI_API_KEY:
        error_response["error"] = "Gemini API key is not configured"
        print("WARNING: GEMINI_API_KEY is not set")
        return error_response
    
    setup_gemini()
    
    # Validate input texts
    if len(resume_text) < 50:
        error_response["error"] = "Resume text is too short or couldn't be properly extracted"
        print(f"Resume text too short: {resume_text}")
        return error_response
    
    if len(jd_text) < 50:
        error_response["error"] = "Job description is too short or couldn't be properly extracted"
        print(f"Job description text too short: {jd_text}")
        return error_response
    
    # Use Gemini-1.5 Pro model
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        print("Successfully created Gemini model for JD matching")
    except Exception as e:
        error_response["error"] = f"Failed to create Gemini model: {str(e)}"
        print(f"Error creating Gemini model: {str(e)}")
        return error_response
    
    # Construct the prompt with clear instructions
    prompt = f"""
    ACT AS AN EXPERT ATS ANALYZER. Analyze how well this resume matches the job description.
    
    RESUME:
    {resume_text}
    
    JOB DESCRIPTION:
    {jd_text}
    
    YOUR ANALYSIS MUST INCLUDE:
    1. Overall match score (0-100%)
    2. List of matching skills (exact matches only)
    3. List of missing skills (clearly missing from resume)
    4. Specific recommendations to improve the resume
    5. Category match scores (Technical Skills, Experience, Education, Soft Skills, Industry Knowledge)
    
    RESPONSE FORMAT (STRICT JSON ONLY):
    {{
        "score": 75,
        "matching_skills": ["Python", "Project Management"],
        "missing_skills": ["AWS", "Docker"],
        "recommendations": [
            "Add AWS certification",
            "Highlight Docker experience"
        ],
        "category_scores": {{
            "Technical Skills": 80,
            "Experience": 70,
            "Education": 90,
            "Soft Skills": 65,
            "Industry Knowledge": 75
        }}
    }}
    
    IMPORTANT:
    - Only respond with valid JSON
    - Do not include any markdown formatting
    - Ensure all numbers are integers
    - All arrays should contain at least 3 items if possible
    """
    
    try:
        print("Sending request to Gemini API for JD matching...")
        response = model.generate_content(prompt)
        print("Received response from Gemini API")
        
        # Get the text response
        response_text = response.text if hasattr(response, 'text') else str(response)
        print(f"Raw response: {response_text[:200]}...")
        
        # Clean and parse the response
        result = parse_gemini_response(response_text)
        
        # Validate the result structure
        return validate_result_structure(result)
        
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        error_response["error"] = str(e)
        return error_response

def parse_gemini_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the Gemini response into a structured dictionary
    Handles both JSON and text responses
    """
    # First try to extract JSON from markdown code block
    json_match = re.search(r'```json\s*({.+?})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON directly in the response
    json_str = response_text.strip()
    if not (json_str.startswith('{') and json_str.endswith('}')):
        # Try to find the JSON object in the text
        start_idx = json_str.find('{')
        end_idx = json_str.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = json_str[start_idx:end_idx+1]
    
    # Try to parse as JSON
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print("Failed to parse as JSON, using fallback parser")
        return parse_text_response(response_text)

def parse_text_response(text: str) -> Dict[str, Any]:
    """
    Parse a text response when JSON parsing fails
    """
    result = {
        "score": 0,
        "matching_skills": [],
        "missing_skills": [],
        "recommendations": [],
        "category_scores": {
            "Technical Skills": 0,
            "Experience": 0,
            "Education": 0,
            "Soft Skills": 0,
            "Industry Knowledge": 0
        }
    }
    
    # Extract score
    score_match = re.search(r'"score":\s*(\d+)', text)
    if not score_match:
        score_match = re.search(r'score[:\s]*(\d+)', text, re.IGNORECASE)
    if score_match:
        result["score"] = int(score_match.group(1))
    
    # Extract matching skills
    match_skills_section = extract_section(text, "matching skills")
    if match_skills_section:
        result["matching_skills"] = extract_list_items(match_skills_section)
    
    # Extract missing skills
    missing_skills_section = extract_section(text, "missing skills")
    if missing_skills_section:
        result["missing_skills"] = extract_list_items(missing_skills_section)
    
    # Extract recommendations
    recommendations_section = extract_section(text, "recommendations")
    if recommendations_section:
        result["recommendations"] = extract_list_items(recommendations_section)
    
    # Extract category scores
    for category in result["category_scores"].keys():
        category_match = re.search(fr'{category}[:\s]*(\d+)', text, re.IGNORECASE)
        if category_match:
            result["category_scores"][category] = int(category_match.group(1))
    
    return result

def extract_section(text: str, section_name: str) -> str:
    """
    Extract a section from the response text
    """
    pattern = fr'{section_name}[:\s]*\n?(.*?)(?=\n\w+[:\s]|\n*$)'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_list_items(text: str) -> List[str]:
    """
    Extract list items from a section of text
    """
    items = []
    # Match bullet points
    bullet_items = re.findall(r'[-*•]\s*(.+?)(?=\n[-*•]|\n\d+\.|\n\w+|\n*$)', text, re.DOTALL)
    items.extend([item.strip() for item in bullet_items])
    
    # Match numbered items
    numbered_items = re.findall(r'\d+\.\s*(.+?)(?=\n\d+\.|\n[-*•]|\n\w+|\n*$)', text, re.DOTALL)
    items.extend([item.strip() for item in numbered_items])
    
    # Match lines that look like list items
    if not items:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        items.extend(lines[:5])  # Take first 5 lines as fallback
    
    return items[:10]  # Return max 10 items

def validate_result_structure(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure the result has all required fields with proper types
    """
    # Default structure
    validated = {
        "score": 0,
        "matching_skills": [],
        "missing_skills": [],
        "recommendations": [],
        "category_scores": {
            "Technical Skills": 0,
            "Experience": 0,
            "Education": 0,
            "Soft Skills": 0,
            "Industry Knowledge": 0
        }
    }
    
    # Validate score
    if isinstance(result.get("score"), (int, float)):
        validated["score"] = min(100, max(0, int(result["score"])))
    
    # Validate lists
    for field in ["matching_skills", "missing_skills", "recommendations"]:
        if field in result and isinstance(result[field], list):
            validated[field] = [str(item) for item in result[field]][:20]  # Limit to 20 items
    
    # Validate category scores
    if "category_scores" in result and isinstance(result["category_scores"], dict):
        for category in validated["category_scores"].keys():
            if category in result["category_scores"] and isinstance(result["category_scores"][category], (int, float)):
                validated["category_scores"][category] = min(100, max(0, int(result["category_scores"][category])))
    
    return validated