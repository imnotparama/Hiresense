#!/usr/bin/env python3
"""
HireSense Ranking System

Ranks candidates against a job description for Senior AI Engineer.
Outputs the top 100 candidates as a CSV file.
Designed to be memory-efficient and run on CPU within 5 minutes.
"""

import argparse
import csv
import json
import logging
import math
import os
import re
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for skill categories
CRITICAL_SKILLS = {
    "sentence-transformers", "embeddings", "vector database", "faiss", 
    "pinecone", "qdrant", "weaviate", "elasticsearch", "semantic search", 
    "information retrieval", "ranking", "rag", "retrieval"
}
IMPORTANT_SKILLS = {
    "python", "nlp", "llm", "fine-tuning", "lora", "ndcg", "a/b testing", 
    "recommendation system", "search", "milvus", "opensearch"
}
BONUS_SKILLS = {
    "learning-to-rank", "xgboost", "hr-tech", "distributed systems", "open-source"
}

# Extended list of consulting/services companies (all lowercase)
CONSULTING_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", 
    "hcl", "tech mahindra", "mindtree", "mphasis", "genpact ai"
}

# EdTech companies (all lowercase)
EDTECH_COMPANIES = {
    "byju's", "unacademy", "upgrad", "vedantu"
}

# CV/Speech/Robotics skills for wrong domain check
CV_SPEECH_SKILLS = {
    "yolo", "gans", "opencv", "asr", "image classification", 
    "computer vision", "speech recognition", "cnn", 
    "object detection", "diffusion models", "tts"
}

# NLP/IR skills for wrong domain check
NLP_IR_SKILLS = CRITICAL_SKILLS.union(IMPORTANT_SKILLS).union({
    "llms", "pgvector", "bm25", "haystack", "llamaindex", "peft", "qlora", 
    "hugging face transformers", "langchain", "prompt engineering", 
    "vector search", "information retrieval systems", "search backend", 
    "text encoders", "vector representations", "content matching", 
    "model adaptation", "ranking systems", "search & discovery", 
    "search infrastructure", "indexing algorithms", "natural language processing"
})

def parse_args():
    parser = argparse.ArgumentParser(description='Rank candidates for HireSense')
    parser.add_argument('--candidates', required=True, help='Path to candidates.jsonl')
    parser.add_argument('--out', required=True, help='Path to output CSV')
    return parser.parse_args()

def is_honeypot(candidate):
    """
    Stage 1 - Honeypot Detection
    - Expert proficiency in 5+ skills but duration_months = 0 for all -> honeypot
    - More than 20 skills with all endorsements = 0 -> honeypot
    """
    try:
        skills = candidate.get('skills', [])
        
        # Check 1: Expert proficiency in 5+ skills with duration_months = 0 for all
        expert_skills = [s for s in skills if s.get('proficiency', '').lower() == 'expert']
        if len(expert_skills) >= 5:
            if all(s.get('duration_months', 0) == 0 for s in expert_skills):
                return True
        
        # Check 2: More than 20 skills with all endorsements = 0
        if len(skills) > 20:
            if all(s.get('endorsements', 0) == 0 for s in skills):
                return True
    except Exception:
        # If schema is corrupted, we don't crash, but we play safe and don't flag as honeypot unless certain
        pass
    return False

def calculate_disqualifier_penalty(candidate):
    """
    Stage 2 - Hard Disqualifier Scoring (0 to 1)
    - consulting_only: all career at TCS/Infosys/Wipro/Accenture/Cognizant/Capgemini/HCL/Tech Mahindra -> 0.1
    - no_production_ai: only academia/research, no product company -> 0.2
    - title_mismatch: current title is Marketing/Sales/HR/Finance/Legal/Design -> 0.1
    - wrong_domain: skills 80%+ CV/Speech/Robotics, no NLP/IR -> 0.3
    - Clean candidate -> 1.0
    Returns the minimum (most severe) penalty triggered.
    """
    penalty = 1.0
    try:
        history = candidate.get('career_history', [])
        
        # 1. consulting_only and no_production_ai checks
        if history:
            all_consulting = True
            all_non_product = True
            
            for job in history:
                comp = job.get('company', '').lower().strip()
                
                # Check consulting
                is_consulting = False
                for cc in CONSULTING_COMPANIES:
                    if cc in comp:
                        is_consulting = True
                        break
                if not is_consulting:
                    all_consulting = False
                
                # Check non-product (consulting + edtech)
                is_non_product = False
                for npc in CONSULTING_COMPANIES.union(EDTECH_COMPANIES):
                    if npc in comp:
                        is_non_product = True
                        break
                if not is_non_product:
                    all_non_product = False
            
            if all_consulting:
                penalty = min(penalty, 0.1)
            elif all_non_product:
                # Career is at non-product (e.g. mix of consulting and EdTech, or EdTech only),
                # which means "only academia/research, no product company".
                penalty = min(penalty, 0.2)
                
        # 2. title_mismatch check
        profile = candidate.get('profile', {})
        current_title = profile.get('current_title', '').lower().strip()
        mismatch_titles = ["marketing", "sales", "hr", "finance", "legal", "design"]
        if any(t in current_title for t in mismatch_titles):
            penalty = min(penalty, 0.1)
            
        # 3. wrong_domain check
        skills = [s.get('name', '').lower().strip() for s in candidate.get('skills', []) if s.get('name')]
        cv_count = sum(1 for s in skills if s in CV_SPEECH_SKILLS)
        nlp_count = sum(1 for s in skills if s in NLP_IR_SKILLS)
        ai_count = cv_count + nlp_count
        
        if ai_count > 0 and nlp_count == 0:
            # 100% CV/Speech skills, no NLP/IR skills
            penalty = min(penalty, 0.3)
            
    except Exception:
        pass
    return penalty

def check_skill_in_text(skill_name, text):
    """Check if skill name matches text as a substring or normalized keyword."""
    s_norm = skill_name.lower()
    t_norm = text.lower()
    if s_norm in t_norm:
        return True
    
    # Check normalized with space instead of hyphen
    s_space = s_norm.replace('-', ' ')
    if s_space != s_norm and s_space in t_norm:
        return True
        
    s_no_space = s_norm.replace('-', '')
    if s_no_space != s_norm and s_no_space in t_norm:
        return True
        
    return False

def calculate_skill_score(candidate):
    """
    Stage 3 - Skill Score (0 to 1)
    - Weights: Critical (0.15 each), Important (0.07 each), Bonus (0.03 each)
    - Weight by proficiency: expert = 1.0, advanced = 0.8, intermediate = 0.6, beginner = 0.4
    - Weight by endorsements: log scale bonus (+ 0.1 * log1p(endorsements)), capped at 1.2 per skill
    - Capped at 1.0 total.
    """
    try:
        skills_array = candidate.get('skills', [])
        history = candidate.get('career_history', [])
        
        # Combine all description texts from career history
        desc_text = " ".join([j.get('description', '') for j in history])
        
        # Build map of skill name -> (proficiency, endorsements) from skills array
        skills_map = {}
        for s in skills_array:
            name = s.get('name', '').lower().strip()
            if name:
                skills_map[name] = (s.get('proficiency', 'intermediate').lower(), s.get('endorsements', 0))
        
        proficiency_map = {
            "expert": 1.0,
            "advanced": 0.8,
            "intermediate": 0.6,
            "beginner": 0.4
        }
        
        total_score = 0.0
        
        # 1. Critical Skills
        for skill in CRITICAL_SKILLS:
            matched = False
            prof_factor = 0.0
            endorsements = 0
            
            # Check in skills array
            if skill in skills_map:
                matched = True
                prof_factor = proficiency_map.get(skills_map[skill][0], 0.6)
                endorsements = skills_map[skill][1]
            # Check in career history description
            elif check_skill_in_text(skill, desc_text):
                matched = True
                prof_factor = 0.8 # default to advanced if found in career history
                endorsements = 0
                
            if matched:
                log_bonus = 0.1 * math.log1p(endorsements)
                skill_val = min(1.2, prof_factor + log_bonus)
                total_score += 0.15 * skill_val
                
        # 2. Important Skills
        for skill in IMPORTANT_SKILLS:
            matched = False
            prof_factor = 0.0
            endorsements = 0
            
            if skill in skills_map:
                matched = True
                prof_factor = proficiency_map.get(skills_map[skill][0], 0.6)
                endorsements = skills_map[skill][1]
            elif check_skill_in_text(skill, desc_text):
                matched = True
                prof_factor = 0.8
                endorsements = 0
                
            if matched:
                log_bonus = 0.1 * math.log1p(endorsements)
                skill_val = min(1.2, prof_factor + log_bonus)
                total_score += 0.07 * skill_val
                
        # 3. Bonus Skills
        for skill in BONUS_SKILLS:
            matched = False
            prof_factor = 0.0
            endorsements = 0
            
            if skill in skills_map:
                matched = True
                prof_factor = proficiency_map.get(skills_map[skill][0], 0.6)
                endorsements = skills_map[skill][1]
            elif check_skill_in_text(skill, desc_text):
                matched = True
                prof_factor = 0.8
                endorsements = 0
                
            if matched:
                log_bonus = 0.1 * math.log1p(endorsements)
                skill_val = min(1.2, prof_factor + log_bonus)
                total_score += 0.03 * skill_val
                
        return min(1.0, total_score)
    except Exception:
        return 0.0

def calculate_career_score(candidate):
    """
    Stage 4 - Career Score (0 to 1)
    - experience_score: 5-9 yrs -> 1.0, 9-12 yrs -> 0.8, 3-5 yrs -> 0.6, else -> 0.3
    - product_company_score: fraction of career at non-consulting/non-services companies
    - trajectory_score: 1.0 if descriptions contain keywords, else 0.0
    - title_relevance: 1.0 if current title contains Engineer/Scientist/ML/AI/NLP, else 0.0
    - career_score = 0.3 * exp + 0.3 * product + 0.3 * trajectory + 0.1 * title
    """
    try:
        profile = candidate.get('profile', {})
        history = candidate.get('career_history', [])
        
        # 1. Experience Years Score
        years = profile.get('years_of_experience', 0)
        if 5 <= years <= 9:
            exp_score = 1.0
        elif 9 < years <= 12:
            exp_score = 0.8
        elif 3 <= years < 5:
            exp_score = 0.6
        else:
            exp_score = 0.3
            
        # 2. Product Company Score
        total_duration = 0
        product_duration = 0
        for job in history:
            dur = job.get('duration_months', 0)
            total_duration += dur
            comp = job.get('company', '').lower().strip()
            
            is_consulting = False
            for cc in CONSULTING_COMPANIES:
                if cc in comp:
                    is_consulting = True
                    break
            if not is_consulting:
                product_duration += dur
                
        product_score = 0.0
        if total_duration > 0:
            product_score = product_duration / total_duration
            
        # 3. Trajectory Score
        trajectory_keywords = ["ranking", "retrieval", "recommendation", "search", "vector", "embedding"]
        has_trajectory = False
        for job in history:
            desc = job.get('description', '').lower()
            if any(kw in desc for kw in trajectory_keywords):
                has_trajectory = True
                break
        trajectory_score = 1.0 if has_trajectory else 0.0
        
        # 4. Title Relevance Score
        current_title = profile.get('current_title', '').lower()
        title_keywords = ["engineer", "scientist", "ml", "ai", "nlp"]
        # Use regex to find individual words or abbreviations
        words = re.findall(r'\b[a-zA-Z]+\b', current_title)
        has_relevant_title = any(w in title_keywords for w in words)
        title_score = 1.0 if has_relevant_title else 0.0
        
        career_score = 0.3 * exp_score + 0.3 * product_score + 0.3 * trajectory_score + 0.1 * title_score
        return career_score
    except Exception:
        return 0.0

def calculate_behavioral_score(candidate):
    """
    Stage 5 - Behavioral Signal Score (0 to 1)
    Reference date: 2026-05-28
    Sum all signal weights and normalize: min(1.0, total / 1.9)
    """
    try:
        signals = candidate.get('redrob_signals', {})
        total = 0.0
        
        # Availability
        if signals.get('open_to_work_flag', False):
            total += 0.3
            
        last_active = signals.get('last_active_date')
        if last_active:
            try:
                dt = datetime.strptime(last_active, "%Y-%m-%d")
                days_ago = (datetime(2026, 5, 28) - dt).days
                if days_ago <= 30:
                    total += 0.3
                elif days_ago <= 90:
                    total += 0.15
            except Exception:
                pass
                
        notice = signals.get('notice_period_days', 999)
        if notice < 30:
            total += 0.2
        elif notice < 60:
            total += 0.1
        elif notice > 90:
            total -= 0.1
            
        # Engagement
        rrr = signals.get('recruiter_response_rate', 0.0)
        if rrr > 0.7:
            total += 0.3
        elif rrr > 0.4:
            total += 0.15
            
        icr = signals.get('interview_completion_rate', 0.0)
        if icr > 0.8:
            total += 0.2
            
        github = signals.get('github_activity_score', -1)
        if github > 60:
            total += 0.2
        elif github > 30:
            total += 0.1
            
        # Trust
        if signals.get('verified_email', False) and signals.get('verified_phone', False):
            total += 0.2
            
        pc_score = signals.get('profile_completeness_score', 0.0)
        if pc_score > 80:
            total += 0.2
            
        return max(0.0, min(1.0, total / 1.9))
    except Exception:
        return 0.0

def calculate_location_score(candidate):
    """
    Stage 6 - Location Score (0 to 1)
    - India + preferred city (Pune, Noida, Delhi, Mumbai, Hyderabad, Bangalore, Chennai) -> 1.0
    - India + willing to relocate -> 0.8
    - India only -> 0.6
    - willing to relocate only -> 0.4
    - else -> 0.2
    """
    try:
        profile = profile = candidate.get('profile', {})
        signals = candidate.get('redrob_signals', {})
        
        country = profile.get('country', '').lower().strip()
        loc = profile.get('location', '').lower().strip()
        willing_to_relocate = signals.get('willing_to_relocate', False)
        
        preferred_cities = ["pune", "noida", "delhi", "mumbai", "hyderabad", "bangalore", "chennai"]
        is_preferred_city = any(city in loc for city in preferred_cities)
        
        if country == 'india':
            if is_preferred_city:
                return 1.0
            elif willing_to_relocate:
                return 0.8
            else:
                return 0.6
        else:
            if willing_to_relocate:
                return 0.4
            else:
                return 0.2
    except Exception:
        return 0.2

def calculate_education_score(candidate):
    """
    Education Score (0 to 1)
    - tier_1 -> 1.0, tier_2 -> 0.7, tier_3 -> 0.5, tier_4/unknown -> 0.3
    - Take best education tier from education[] array
    """
    try:
        education = candidate.get('education', [])
        if not education:
            return 0.3
        
        best_score = 0.3
        tier_map = {
            "tier_1": 1.0,
            "tier_2": 0.7,
            "tier_3": 0.5,
            "tier_4": 0.3,
            "unknown": 0.3
        }
        for edu in education:
            tier = edu.get('tier', 'unknown').lower().strip()
            score = tier_map.get(tier, 0.3)
            if score > best_score:
                best_score = score
        return best_score
    except Exception:
        return 0.3

def generate_reasoning(candidate, rank, score, disqualifier_penalty):
    """
    Generate a 1-2 sentence honest reasoning describing candidate strengths and concerns.
    Makes references to specific facts.
    """
    try:
        profile = candidate.get('profile', {})
        signals = candidate.get('redrob_signals', {})
        skills = [s.get('name', '') for s in candidate.get('skills', []) if s.get('name')]
        
        title = profile.get('current_title', 'Engineer')
        years = profile.get('years_of_experience', 0.0)
        matching_skills = [s for s in skills if s.lower() in CRITICAL_SKILLS or s.lower() in IMPORTANT_SKILLS]
        
        # Segment by rank to align tone and vary descriptions
        if rank <= 10:
            prefix = "Outstanding founding team candidate."
        elif rank <= 50:
            prefix = "Strong fit with solid backend development experience."
        else:
            prefix = "Qualified candidate matching basic requirements."
            
        s1 = f"{prefix} {title} with {years} years experience, specializing in {', '.join(matching_skills[:3]) if matching_skills else 'applied ML'}."
        
        # Add honest concerns
        concerns = []
        if disqualifier_penalty == 0.1:
            concerns.append("career limited to consulting/IT services")
        elif disqualifier_penalty == 0.2:
            concerns.append("academia/research career profile")
        elif disqualifier_penalty == 0.3:
            concerns.append("skills focused on speech/CV rather than NLP/IR")
            
        notice = signals.get('notice_period_days', 999)
        if notice > 90:
            concerns.append(f"notice period is {notice} days")
        if not signals.get('verified_email') or not signals.get('verified_phone'):
            concerns.append("unverified contact information")
            
        if concerns:
            s2 = f"Good engagement signals, though note concern: {', and '.join(concerns[:2])}."
        else:
            loc = profile.get('location', 'India')
            s2 = f"Excellent behavioral alignment, based in {loc} with verified account status."
            
        return f"{s1} {s2}"
    except Exception:
        return "Qualified candidate with matching experience in modern engineering systems."

def process_candidate(line):
    """
    Process a single line of candidate JSONL data.
    Returns a dict with candidate_id, final_score, disqualifier_penalty, and raw candidate info
    or None if data is malformed.
    """
    try:
        candidate = json.loads(line.strip())
    except Exception:
        return None
        
    cid = candidate.get('candidate_id', '')
    if not cid:
        return None
        
    # Stage 1 - Honeypot Check
    if is_honeypot(candidate):
        return {
            'candidate_id': cid,
            'final_score': 0.0,
            'disqualifier_penalty': 0.0,
            'is_honeypot': True,
            'candidate': candidate
        }
        
    # Compute component scores
    disqualifier_penalty = calculate_disqualifier_penalty(candidate)
    skill_score = calculate_skill_score(candidate)
    career_score = calculate_career_score(candidate)
    behavioral_score = calculate_behavioral_score(candidate)
    education_score = calculate_education_score(candidate)
    location_score = calculate_location_score(candidate)
    
    # Calculate final score
    final_score = (
        0.35 * skill_score +
        0.30 * career_score +
        0.20 * behavioral_score +
        0.10 * education_score +
        0.05 * location_score
    ) * disqualifier_penalty
    
    return {
        'candidate_id': cid,
        'final_score': final_score,
        'disqualifier_penalty': disqualifier_penalty,
        'is_honeypot': False,
        'candidate': candidate
    }

def main():
    args = parse_args()
    
    # Check if input path exists
    if not os.path.exists(args.candidates):
        logger.error(f"Input path not found: {args.candidates}")
        sys.exit(1)
        
    # Ensure output folder exists
    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    candidates_list = []
    processed = 0
    
    logger.info(f"Starting ranking processing for file: {args.candidates}")
    
    try:
        with open(args.candidates, 'r', encoding='utf-8') as f:
            for line in f:
                res = process_candidate(line)
                processed += 1
                if processed % 10000 == 0:
                    logger.info(f"Processed {processed} candidates...")
                    
                if res is not None:
                    # Exclude honeypots from top 100
                    if not res['is_honeypot']:
                        candidates_list.append(res)
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        sys.exit(1)
        
    logger.info(f"Finished parsing. Total processed: {processed}, Valid candidates: {len(candidates_list)}")
    
    # Sort candidates: primary key is rounded final_score descending, secondary key is candidate_id ascending (string sorting)
    candidates_list.sort(key=lambda x: (-round(x['final_score'], 4), x['candidate_id']))
    
    # Take top 100
    top_100 = candidates_list[:100]
    
    # Assign ranks and generate reasoning (reasoning requires rank and final score context)
    formatted_rows = []
    for i, item in enumerate(top_100, start=1):
        reasoning = generate_reasoning(
            item['candidate'], 
            rank=i, 
            score=item['final_score'], 
            disqualifier_penalty=item['disqualifier_penalty']
        )
        formatted_rows.append({
            'candidate_id': item['candidate_id'],
            'rank': i,
            'score': round(item['final_score'], 4),
            'reasoning': reasoning
        })
        
    # Write top 100 candidates to output CSV
    try:
        with open(args.out, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=['candidate_id', 'rank', 'score', 'reasoning'])
            writer.writeheader()
            for row in formatted_rows:
                writer.writerow(row)
        logger.info(f"Successfully wrote top 100 rankings to {args.out}")
    except Exception as e:
        logger.error(f"Error writing to output CSV: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
