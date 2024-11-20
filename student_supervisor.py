# student_supervisor.py

import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from typing import List, Dict, Tuple, Any
import pandas as pd
from collections import defaultdict
import json
import matplotlib.pyplot as plt
import seaborn as sns

# Define domain weights as a global constant
DOMAIN_WEIGHTS = {
    'research_alignment': 0.4,
    'methodology_match': 0.3,
    'technical_skills': 0.2,
    'domain_knowledge': 0.1
}

class AdvancedSupervisorMatcher:
    def __init__(self):
        # Initialize NLTK
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
        nltk.download('wordnet', quiet=True)
        self.stop_words = set(stopwords.words('english'))
        
        # Load BERT model
        print("Loading BERT model...")
        self.tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
        self.model = AutoModel.from_pretrained('bert-base-uncased')
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = self.model.to(self.device)
        self.model.eval()
        
        # Initialize TF-IDF vectorizer
        self.tfidf = TfidfVectorizer(stop_words='english')
        
        # Domain-specific weights
        self.domain_weights = DOMAIN_WEIGHTS
        
        # Technical skills dictionary
        self.technical_skills = {
            'programming': ['python', 'java', 'c++', 'r', 'matlab'],
            'machine_learning': ['tensorflow', 'pytorch', 'scikit-learn', 'keras'],
            'data_analysis': ['pandas', 'numpy', 'data mining', 'statistical analysis'],
            'cloud': ['aws', 'azure', 'google cloud', 'cloud computing']
        }
        
        # Research methodology terms
        self.methodology_terms = {
            'quantitative': ['statistical analysis', 'empirical study', 'quantitative methods'],
            'qualitative': ['qualitative analysis', 'case study', 'ethnography'],
            'mixed_methods': ['mixed methods', 'triangulation', 'multi-method'],
            'experimental': ['experimental design', 'controlled study', 'randomized trial']
        }

    def get_bert_embedding(self, text: str) -> np.ndarray:
        """Get BERT embedding with attention masking"""
        inputs = self.tokenizer(text, padding=True, truncation=True,
                              max_length=512, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            embeddings = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            
        return embeddings.cpu().numpy()

    def calculate_research_alignment(self, student_desc: str, supervisor_interests: str) -> float:
        """Calculate research topic alignment using BERT embeddings"""
        student_emb = self.get_bert_embedding(student_desc)
        supervisor_emb = self.get_bert_embedding(supervisor_interests)
        return float(cosine_similarity(student_emb, supervisor_emb)[0][0])

    def extract_technical_skills(self, text: str) -> Dict[str, List[str]]:
        """Extract technical skills mentioned in text"""
        text_lower = text.lower()
        found_skills = defaultdict(list)
        
        for category, skills in self.technical_skills.items():
            for skill in skills:
                if skill in text_lower:
                    found_skills[category].append(skill)
        
        return dict(found_skills)

    def calculate_methodology_match(self, student_desc: str, supervisor_interests: str) -> float:
        """Calculate methodology alignment score"""
        student_methods = self._extract_methodology(student_desc)
        supervisor_methods = self._extract_methodology(supervisor_interests)
        
        if not student_methods or not supervisor_methods:
            return 0.5  # Neutral score if methodology not specified
            
        common_methods = set(student_methods) & set(supervisor_methods)
        return len(common_methods) / max(len(student_methods), len(supervisor_methods))

    def _extract_methodology(self, text: str) -> List[str]:
        """Extract research methodology terms from text"""
        text_lower = text.lower()
        found_methods = []
        
        for category, terms in self.methodology_terms.items():
            for term in terms:
                if term in text_lower:
                    found_methods.append(category)
                    break
        
        return found_methods

    def calculate_domain_knowledge(self, student_desc: str, supervisor_interests: str) -> float:
        """Calculate domain-specific knowledge alignment"""
        # Use TF-IDF to identify domain-specific terms
        tfidf_matrix = self.tfidf.fit_transform([student_desc, supervisor_interests])
        feature_names = self.tfidf.get_feature_names_out()
        
        # Get important terms for both documents
        student_terms = set(feature_names[i] for i in tfidf_matrix[0].nonzero()[1])
        supervisor_terms = set(feature_names[i] for i in tfidf_matrix[1].nonzero()[1])
        
        # Calculate Jaccard similarity for domain terms
        if not student_terms or not supervisor_terms:
            return 0.5
        
        return len(student_terms & supervisor_terms) / len(student_terms | supervisor_terms)

    def match_supervisors(self, student_data: Dict[str, Any], 
                         supervisors: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Advanced matching with multiple criteria"""
        results = []
        
        for supervisor in supervisors:
            # Calculate various matching scores
            research_score = self.calculate_research_alignment(
                student_data['project_description'],
                supervisor['interests']
            )
            
            methodology_score = self.calculate_methodology_match(
                student_data['project_description'],
                supervisor['interests']
            )
            
            # Extract and compare technical skills
            student_skills = self.extract_technical_skills(student_data['project_description'])
            supervisor_skills = self.extract_technical_skills(supervisor['interests'])
            
            # Calculate technical skills overlap
            all_skills = set(skill for skills in student_skills.values() for skill in skills)
            all_sup_skills = set(skill for skills in supervisor_skills.values() for skill in skills)
            technical_score = len(all_skills & all_sup_skills) / max(len(all_skills | all_sup_skills), 1)
            
            # Calculate domain knowledge score
            domain_score = self.calculate_domain_knowledge(
                student_data['project_description'],
                supervisor['interests']
            )
            
            # Calculate weighted final score
            final_score = (
                self.domain_weights['research_alignment'] * research_score +
                self.domain_weights['methodology_match'] * methodology_score +
                self.domain_weights['technical_skills'] * technical_score +
                self.domain_weights['domain_knowledge'] * domain_score
            )
            
            # Compile detailed results
            results.append({
                'supervisor_name': supervisor['name'],
                'final_score': final_score,
                'detailed_scores': {
                    'research_alignment': research_score,
                    'methodology_match': methodology_score,
                    'technical_skills': technical_score,
                    'domain_knowledge': domain_score
                },
                'matching_skills': list(all_skills & all_sup_skills),
                'methodology_overlap': self._extract_methodology(supervisor['interests'])
            })
        
        # Sort by final score
        return sorted(results, key=lambda x: x['final_score'], reverse=True)

def visualize_results(matches: List[Dict[str, Any]], output_file: str = 'matching_results.png'):
    """Create visualization of matching results"""
    plt.figure(figsize=(12, 6))
    
    # Prepare data for visualization
    supervisors = [m['supervisor_name'] for m in matches]
    scores = [m['detailed_scores'] for m in matches]
    
    # Create stacked bar chart
    bottom = np.zeros(len(supervisors))
    
    # Use the global DOMAIN_WEIGHTS
    for category, weight in DOMAIN_WEIGHTS.items():
        values = [s[category] * weight for s in scores]
        plt.bar(supervisors, values, bottom=bottom, label=category)
        bottom += values
    
    plt.title('Supervisor Matching Scores Breakdown')
    plt.xlabel('Supervisors')
    plt.ylabel('Weighted Score')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save plot
    plt.savefig(output_file)
    plt.close()

def generate_report(student_data: Dict[str, Any], matches: List[Dict[str, Any]]) -> str:
    """Generate detailed matching report"""
    report = [
        f"Matching Report for {student_data['student_name']}",
        "=" * 50,
        "\nProject Description:",
        student_data['project_description'].strip(),
        "\nTop Matches:",
        "-" * 50
    ]
    
    for i, match in enumerate(matches, 1):
        report.extend([
            f"\n{i}. {match['supervisor_name']} (Overall Score: {match['final_score']:.3f})",
            "\nDetailed Scores:",
            f"- Research Alignment: {match['detailed_scores']['research_alignment']:.3f}",
            f"- Methodology Match: {match['detailed_scores']['methodology_match']:.3f}",
            f"- Technical Skills: {match['detailed_scores']['technical_skills']:.3f}",
            f"- Domain Knowledge: {match['detailed_scores']['domain_knowledge']:.3f}",
            "\nMatching Skills:",
            ", ".join(match['matching_skills']) if match['matching_skills'] else "None found",
            "\nMethodology Overlap:",
            ", ".join(match['methodology_overlap']) if match['methodology_overlap'] else "None found",
            "\n" + "-" * 50
        ])
    
    return "\n".join(report)