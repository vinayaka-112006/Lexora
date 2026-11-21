import sys
sys.path.insert(0, 'rag-service')
from app.answer_postprocessor import postprocess_generated_answer, _asserts_fabricated_legal_instrument, _bda_section7_scope_is_overgeneralized, _claim_safety_guards

section7 = {
    'chunk_id': 'bda-s7', 'document_id': 'biological_diversity_act_2002',
    'document_name': 'Biological Diversity Act, 2002', 'jurisdiction': 'India',
    'provision_type': 'section', 'provision_number': '7',
    'page_start': 7, 'page_end': 8,
    'text': (
        'No person, other than those referred to in Section 3(2), shall, without prior intimation '
        'to the State Biodiversity Board, obtain any biological resource occurring in India or '
        'knowledge associated thereto for commercial utilisation. '
        'Provided that the provisions of this section shall not apply in relation to cultivated '
        'medicinal plants and their products where a certificate of origin is obtained.'
    ),
}
claim = "Section 7 of the Biological Diversity Act, 2002 requires prior intimation."
print('safety guards:', _claim_safety_guards(claim, 'What does Section 7 require?', [section7]))
print('bda_section7_scope_is_overgeneralized:', _bda_section7_scope_is_overgeneralized(claim, [section7]))
print('fabricated:', _asserts_fabricated_legal_instrument(claim, [section7]))

answer = 'Section 7 of the Biological Diversity Act, 2002 requires prior intimation. [Source: Biological Diversity Act, 2002, section 7, pp. 7-8]'
result = postprocess_generated_answer('What does Section 7 require?', answer, [section7])
import json
print('Answer:', result['answer'])
print('Decision:', result['confidence']['decision'])
print('Generated claims withheld_reasons:')
for c in result['claim_verification'].get('generated_claims', []):
    print(' ', c['claim_id'], c.get('withheld_reasons'), c.get('safety_guards'))

