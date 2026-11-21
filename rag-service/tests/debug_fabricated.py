import sys
sys.path.insert(0, 'rag-service')
from app.answer_postprocessor import postprocess_generated_answer, _asserts_fabricated_legal_instrument

section7 = {
    'chunk_id': 'bda-s7', 'document_id': 'biological_diversity_act_2002',
    'document_name': 'Biological Diversity Act, 2002', 'jurisdiction': 'India',
    'provision_type': 'section', 'provision_number': '7',
    'page_start': 7, 'page_end': 8,
    'text': 'No person shall, without prior intimation to the State Biodiversity Board, obtain any biological resource.',
}
answer = 'Section 7 of the Biological Diversity Act, 2002 requires prior intimation. [Source: Biological Diversity Act, 2002, section 7, pp. 7-8]'
result = postprocess_generated_answer('What does Section 7 require?', answer, [section7])
import json
print('Answer:', result['answer'])
print('Decision:', result['confidence']['decision'])
print('Generated claims:', json.dumps(result['claim_verification'].get('generated_claims', []), indent=2, default=str))
print()
print('Fabricated check on "Section 7 of the Biological Diversity Act, 2002 requires prior intimation.":', 
      _asserts_fabricated_legal_instrument('Section 7 of the Biological Diversity Act, 2002 requires prior intimation.', [section7]))

