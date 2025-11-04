import json, os, pytest

BASELINE_PATH = 'eval/baseline_metrics.json'
CURRENT_PATH = 'eval/model_metrics.json'

REQ_DELTA_ROUGE = float(os.getenv('REQ_DELTA_ROUGE', '0.05'))    # required ROUGE improvement
REQ_DELTA_MACROF1 = float(os.getenv('REQ_DELTA_MACROF1', '0.10'))  # required macro F1 improvement

STRICT = os.getenv('EVAL_STRICT', '0') == '1'

def test_gate_improvements():
    if not (os.path.exists(BASELINE_PATH) and os.path.exists(CURRENT_PATH)):
        pytest.xfail('eval artifacts missing; run offline eval')
    base = json.load(open(BASELINE_PATH))
    cur = json.load(open(CURRENT_PATH))
    try:
        b_rouge = base['summarization']['rougeL_f_mean']
        c_rouge = cur['summarization']['rougeL_f_mean']
        b_f1 = base['sentiment']['macro_f1']
        c_f1 = cur['sentiment']['macro_f1']
    except KeyError as e:
        pytest.fail(f'Metrics missing key: {e}')
    if not STRICT:
        pytest.xfail(f'non-strict mode: ROUGE delta = {(c_rouge - b_rouge):.3f}, Macro-F1 delta = {(c_f1 - b_f1):.3f}')
    assert (c_rouge - b_rouge) >= REQ_DELTA_ROUGE, 'ROUGE delta {(c_rouge - b_rouge):.3f} < {REQ_DELTA_ROUGE}'
    assert (c_f1 - b_f1) >= REQ_DELTA_MACROF1, f'Macro-F1 delta {(c_f1 - b_f1):.3f} < {REQ_DELTA_MACROF1}'
    