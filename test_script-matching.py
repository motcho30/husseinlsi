# test_advanced_matching.py

from student_supervisor import AdvancedSupervisorMatcher, visualize_results, generate_report
import json
from datetime import datetime

def test_advanced_matching():
    # Comprehensive test data
    student_projects = [
        {
            'student_name': 'Alice Smith',
            'project_description': """
            Developing an advanced deep learning framework for medical image analysis, 
            specifically focusing on early detection of lung abnormalities in chest X-rays 
            using convolutional neural networks. The project involves implementing transfer 
            learning techniques with PyTorch and TensorFlow, utilizing AWS for cloud 
            computing, and applying statistical analysis for validation. The methodology 
            includes both quantitative analysis of model performance and qualitative 
            evaluation by medical professionals.
            """
        },
        {
            'student_name': 'Bob Johnson',
            'project_description': """
            Research on natural language processing using transformer architectures 
            for multilingual sentiment analysis. The project employs BERT models and 
            Python-based deep learning frameworks, with a focus on low-resource languages. 
            Methodology includes mixed-methods approach combining statistical analysis 
            of model performance with case studies of specific language pairs. Using 
            Azure cloud services for large-scale model training and evaluation.
            """
        },
        {
            'student_name': 'Carol Zhang',
            'project_description': """
            Investigating blockchain security protocols using formal verification methods. 
            Implementation in Solidity and Python, with emphasis on smart contract 
            vulnerability detection. The research methodology follows an experimental 
            design approach, including controlled testing of different attack vectors. 
            Using statistical analysis and machine learning for pattern recognition in 
            security breaches, implemented with scikit-learn and pandas.
            """
        }
    ]

    supervisors = [
        {
            'name': 'Dr. Sarah Chen',
            'interests': """
            Deep Learning, Computer Vision, Medical Image Analysis, Neural Networks. 
            Experienced in PyTorch, TensorFlow, and cloud computing platforms. 
            Research methodology combines quantitative analysis with clinical validation. 
            Current projects focus on transfer learning and statistical validation of 
            AI in healthcare applications.
            """
        },
        {
            'name': 'Dr. Emily Watson',
            'interests': """
            Natural Language Processing, BERT Models, Transformer Architectures. 
            Expertise in Python, PyTorch, and multilingual NLP systems. Mixed-methods 
            research approach, specializing in low-resource languages and cross-lingual 
            transfer learning. Experience with cloud-based distributed training.
            """
        },
        {
            'name': 'Dr. James Wilson',
            'interests': """
            Machine Learning, Neural Networks, Deep Learning, Statistical Analysis. 
            Proficient in TensorFlow, scikit-learn, and R. Quantitative research 
            methods with focus on empirical validation. Experience in both supervised 
            and unsupervised learning approaches.
            """
        },
        {
            'name': 'Dr. Michael Brown',
            'interests': """
            Blockchain Technology, Cryptography, Smart Contracts. Expertise in 
            Solidity, Python, and formal verification methods. Experimental research 
            methodology focusing on security protocol analysis. Experience with 
            statistical analysis and machine learning for security applications.
            """
        },
        {
            'name': 'Dr. Lisa Thompson',
            'interests': """
            Data Mining, Statistical Learning, Predictive Modeling. Skilled in R, 
            Python, and SQL. Mixed-methods research approach combining statistical 
            analysis with case studies. Focus on reproducible research and 
            empirical validation.
            """
        }
    ]

    try:
        # Initialize matcher
        print("Initializing advanced matching system...")
        matcher = AdvancedSupervisorMatcher()

        # Process each student
        for student in student_projects:
            print(f"\n{'='*80}")
            print(f"Processing student: {student['student_name']}")
            print(f"{'='*80}")

            # Get matches
            matches = matcher.match_supervisors(student, supervisors)

            # Generate and save visualization
            output_file = f"matching_results_{student['student_name'].lower().replace(' ', '_')}.png"
            visualize_results(matches, output_file)
            print(f"\nVisualization saved as: {output_file}")

            # Generate and save detailed report
            report = generate_report(student, matches)
            report_file = f"matching_report_{student['student_name'].lower().replace(' ', '_')}.txt"
            with open(report_file, 'w') as f:
                f.write(report)
            print(f"Detailed report saved as: {report_file}")

            # Save raw matching data
            matching_data = {
                'student': student,
                'matches': matches,
                'timestamp': datetime.now().isoformat(),
                'matching_version': '2.0'
            }
            json_file = f"matching_data_{student['student_name'].lower().replace(' ', '_')}.json"
            with open(json_file, 'w') as f:
                json.dump(matching_data, f, indent=2)
            print(f"Raw matching data saved as: {json_file}")

            # Print summary
            print("\nTop 3 Matches:")
            print("-" * 50)
            for i, match in enumerate(matches[:3], 1):
                print(f"{i}. {match['supervisor_name']}: {match['final_score']:.3f}")
                print(f"   Research Alignment: {match['detailed_scores']['research_alignment']:.3f}")
                print(f"   Methodology Match: {match['detailed_scores']['methodology_match']:.3f}")
                print(f"   Technical Skills: {match['detailed_scores']['technical_skills']:.3f}")
                print(f"   Domain Knowledge: {match['detailed_scores']['domain_knowledge']:.3f}")
                if match['matching_skills']:
                    print(f"   Matching Skills: {', '.join(match['matching_skills'])}")
                print()

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise e

if __name__ == "__main__":
    test_advanced_matching()