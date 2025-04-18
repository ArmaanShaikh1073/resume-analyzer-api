import google.generativeai as genai
from app.config import settings
import json

def setup_gemini():
    """
    Configure the Gemini API client
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    print("Gemini API configured")

def analyze_resume(resume_text: str) -> dict:
    """
    Analyze resume text using Gemini API
    """
    print(f"Starting analysis of resume text ({len(resume_text)} characters)")
    
    # Check if API key is set
    if not settings.GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY is not set")
        return {
            "error": "Gemini API key is not configured",
            "strengths": ["API key missing"],
            "areas_of_improvement": ["Configure Gemini API key"],
            "project_recommendations": ["Set up proper API configuration"],
            "career_roadmap": "Please configure the Gemini API key to get results",
            "recommended_courses": ["API configuration course"]
        }
    
    setup_gemini()
    
    # Use Gemini-1.5 Pro model
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        print("Successfully created Gemini model")
    except Exception as e:
        print(f"Error creating Gemini model: {str(e)}")
        return {
            "error": f"Failed to create Gemini model: {str(e)}",
            "strengths": [],
            "areas_of_improvement": [],
            "project_recommendations": [],
            "career_roadmap": "Error occurred during analysis setup",
            "recommended_courses": []
        }
    
    # If resume text is too short, return error
    if len(resume_text) < 50:
        print(f"Resume text too short: {resume_text}")
        return {
            "error": "Resume text is too short or couldn't be properly extracted",
            "strengths": ["Unable to analyze - resume text too short"],
            "areas_of_improvement": ["Provide a more complete resume"],
            "project_recommendations": [],
            "career_roadmap": "Please provide a more detailed resume for analysis",
            "recommended_courses": []
        }
    
    # Construct the prompt for resume analysis
    prompt = f"""
    You are an expert resume analyzer and career advisor. 
    Analyze the following resume carefully and provide detailed feedback.
    
    Resume Text:
    {resume_text}
    
    Please provide the following details in your analysis:
    1. Strengths: Identify the key strengths of the candidate based on their resume.
    2. Areas of Improvement: Identify areas where the candidate could improve.
    3. Project Recommendations: Based on their skills, suggest 3-5 projects they could build to showcase their abilities.
    4. Career Roadmap: Suggest a 1-2 year roadmap for career growth.
    5. Recommended Courses: Suggest 3-5 specific courses or certifications that would benefit them.
    
    Format your response in JSON like this:
    {{
      "strengths": ["strength1", "strength2", "strength3"],
      "areas_of_improvement": ["area1", "area2", "area3"],
      "project_recommendations": ["project1", "project2", "project3"],
      "career_roadmap": "Detailed career roadmap goes here...",
      "recommended_courses": ["course1", "course2", "course3"]
    }}
    """
    
    try:
        print("Sending request to Gemini API...")
        # Generate response from Gemini
        response = model.generate_content(prompt)
        print("Received response from Gemini API")
        
        # Get the text response
        if hasattr(response, 'text'):
            response_text = response.text
        else:
            response_text = str(response)
            
        print(f"Response preview: {response_text[:200]}...")
        
        # Try to parse as JSON
        try:
            # First, try to find JSON in the response
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                json_str = json_match.group(1)
                print("Found JSON in code block")
            else:
                json_str = response_text
            
            # Clean up the string to help with parsing
            json_str = json_str.strip()
            if not (json_str.startswith('{') and json_str.endswith('}')):
                # Try to find the JSON object
                start_idx = json_str.find('{')
                end_idx = json_str.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    json_str = json_str[start_idx:end_idx+1]
                    print(f"Extracted JSON object: {json_str[:50]}...")
            
            # Parse JSON
            result = json.loads(json_str)
            print("Successfully parsed JSON response")
            
            # Ensure all required fields exist
            required_fields = ["strengths", "areas_of_improvement", "project_recommendations", 
                              "career_roadmap", "recommended_courses"]
            
            for field in required_fields:
                if field not in result:
                    result[field] = [] if field != "career_roadmap" else "No information provided"
            
            return result
            
        except Exception as json_error:
            print(f"Failed to parse JSON: {str(json_error)}")
            # If parsing fails, use our custom parser
            result = parse_gemini_response(response_text)
            print(f"Used custom parser, found {len(result['strengths'])} strengths")
            return result
            
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        # Handle API errors
        return {
            "error": str(e),
            "strengths": ["Error occurred during analysis"],
            "areas_of_improvement": ["Try again later"],
            "project_recommendations": [],
            "career_roadmap": f"Error occurred during analysis: {str(e)}",
            "recommended_courses": []
        }

def parse_gemini_response(response_text: str) -> dict:
    """
    Attempt to parse the Gemini response into a structured format
    Even if the model doesn't return valid JSON
    """
    print("Using custom parser for Gemini response")
    
    result = {
        "strengths": [],
        "areas_of_improvement": [],
        "project_recommendations": [],
        "career_roadmap": "",
        "recommended_courses": [],
        "raw_analysis": response_text
    }
    
    # Simple parsing logic if JSON parsing fails
    sections = {
        "strengths": ["strength", "strengths", "strong points"],
        "areas_of_improvement": ["improvement", "weaknesses", "areas of improvement", "improve"],
        "project_recommendations": ["project", "projects", "build", "create"],
        "career_roadmap": ["roadmap", "career path", "growth path"],
        "recommended_courses": ["courses", "certification", "learn", "study"]
    }
    
    # Split by common headers and look for sections
    lines = response_text.split("\n")
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line is a header
        lower_line = line.lower()
        found_section = False
        
        for section, keywords in sections.items():
            if any(keyword in lower_line for keyword in keywords) and (":" in line or "#" in line or "." in line[:2]):
                current_section = section
                found_section = True
                print(f"Found section: {section}")
                break
        
        # If it's content for a section
        if current_section and not found_section:
            # Handle list items
            if line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
                item = line.lstrip("- *•").strip()
                if current_section in ["strengths", "areas_of_improvement", "project_recommendations", "recommended_courses"]:
                    result[current_section].append(item)
                    print(f"Added item to {current_section}: {item[:30]}...")
            # Handle numbered items
            elif re.match(r'^\d+\.', line):
                item = re.sub(r'^\d+\.', '', line).strip()
                if current_section in ["strengths", "areas_of_improvement", "project_recommendations", "recommended_courses"]:
                    result[current_section].append(item)
                    print(f"Added numbered item to {current_section}: {item[:30]}...")
            # Handle plain text
            elif current_section == "career_roadmap":
                result[current_section] += line + "\n"
    
    # If we found nothing, try to extract some basic information
    if not any([result["strengths"], result["areas_of_improvement"], result["project_recommendations"], result["career_roadmap"], result["recommended_courses"]]):
        print("No structured content found, using fallback extraction")
        # Fallback: split response into sections and try to categorize
        paragraphs = response_text.split("\n\n")
        
        if len(paragraphs) >= 5:
            # Assume the first few paragraphs might correspond to our sections
            result["strengths"] = [paragraphs[0]]
            result["areas_of_improvement"] = [paragraphs[1]]
            result["project_recommendations"] = [paragraphs[2]]
            result["career_roadmap"] = paragraphs[3]
            result["recommended_courses"] = [paragraphs[4]]
    
    # Ensure something is returned for each section
    if not result["strengths"]:
        result["strengths"] = ["Could not extract strengths from analysis"]
    if not result["areas_of_improvement"]:
        result["areas_of_improvement"] = ["Could not extract areas of improvement from analysis"]
    if not result["project_recommendations"]:
        result["project_recommendations"] = ["Could not extract project recommendations from analysis"]
    if not result["career_roadmap"]:
        result["career_roadmap"] = "Could not extract career roadmap from analysis"
    if not result["recommended_courses"]:
        result["recommended_courses"] = ["Could not extract recommended courses from analysis"]
        
    print(f"Final parse results: {len(result['strengths'])} strengths, {len(result['areas_of_improvement'])} improvements")
    return result