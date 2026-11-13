import copy,unittest
from run_processing_layout_qa import accepted_result

class LayoutEvidenceTests(unittest.TestCase):
    def record(self):
        return {"run_id":"fresh","status":"PASS","execution_environment":"ANDROID_X86_64_EMULATOR_NOT_PHONE",
                "scope":"RENDERED_PROCESSING_UI_STATES_NO_INFERENCE","rows":[
                    {"font_scale":s,"state_index":i,"overflow_count":0,"progress_top_px":100*s}
                    for s in (1.0,1.3,2.0) for i in range(7)]}
    def test_complete_current_result_is_accepted(self):
        self.assertTrue(accepted_result("OK (1 test)",self.record(),"fresh"))
    def test_shell_success_stale_or_partial_result_is_refused(self):
        for output in ("", "OK (0 tests)","FAILURES!!! Tests run: 1"):
            self.assertFalse(accepted_result(output,self.record(),"fresh"))
        self.assertFalse(accepted_result("OK (1 test)",self.record(),"other"))
        record=self.record();record["rows"].pop()
        self.assertFalse(accepted_result("OK (1 test)",record,"fresh"))
    def test_coverage_cannot_be_faked_by_duplicate_rows(self):
        record=self.record();record["rows"][-1]=copy.deepcopy(record["rows"][0])
        self.assertFalse(accepted_result("OK (1 test)",record,"fresh"))
    def test_clipping_geometry_or_wrong_environment_is_refused(self):
        for field,value in [("overflow_count",1),("progress_top_px",200),("progress_top_px",float("nan"))]:
            record=self.record();record["rows"][0][field]=value
            self.assertFalse(accepted_result("OK (1 test)",record,"fresh"))
        record=self.record();record["execution_environment"]="PHONE"
        self.assertFalse(accepted_result("OK (1 test)",record,"fresh"))

if __name__=="__main__":unittest.main()
