"""Offline synthetic-only regression for the APEX TIFF rename example."""
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples' / 'tiff_ocr_batch'))
import batch_tiff_renamer as m

class TiffDemoTests(unittest.TestCase):
    def test_safe_stems(self):
        self.assertEqual(m.safe_stem('Invoice # ABC-123 / 2026'), 'Invoice_ABC-123_2026')
        for value in ('...', '', 'CON'):
            with self.assertRaises(ValueError): m.safe_stem(value)

    def test_dry_run_has_no_renames(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.tif';p.write_bytes(b'fictional')
            with patch.object(m,'extract_text',return_value='Invoice: ABC-12'):
                plan=m.make_plan([p],r'Invoice:\s+(\S+)')
            self.assertEqual(plan[0].status,'ready'); self.assertTrue(p.exists())
            self.assertFalse((p.parent/'ABC-12.tif').exists())
            applied=m.apply_plan(plan)
            self.assertEqual(applied[0].status,'renamed')
            self.assertFalse(p.exists());self.assertTrue((p.parent/'ABC-12.tif').exists())

    def test_no_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p=d/'source.tiff';p.write_bytes(b'fictional')
            (d/'ABC-12.tiff').write_bytes(b'existing')
            with patch.object(m,'extract_text',return_value='Invoice: ABC-12'):
                plan=m.make_plan([p],r'Invoice:\s+(\S+)')
            self.assertEqual(plan[0].status,'blocked')
            with self.assertRaises(ValueError): m.apply_plan(plan)
            self.assertEqual((d/'ABC-12.tiff').read_bytes(),b'existing')

    def test_duplicate_targets_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);paths=[d/'1.tif',d/'2.tif']
            for p in paths:p.write_bytes(b'fictional')
            with patch.object(m,'extract_text',return_value='Invoice: ABC-12'):
                plan=m.make_plan(paths,r'Invoice:\s+(\S+)')
            self.assertEqual([x.status for x in plan],['ready','blocked'])
            self.assertTrue(all(p.exists() for p in paths))

    def test_missing_match_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'1.tif';p.write_bytes(b'fictional')
            with patch.object(m,'extract_text',return_value='No recognizable label'):
                plan=m.make_plan([p],r'Invoice:\s+(\S+)')
            self.assertEqual(plan[0].status,'skipped')

    def test_filename_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);target=d/'real.tif';target.write_bytes(b'fictional')
            symlink=d/'link.tif';symlink.symlink_to(target)
            self.assertEqual(m.make_plan([symlink],r'(any)')[0].status,'blocked')

    def test_pattern_capture_required(self):
        with self.assertRaises(ValueError):m.make_plan([],r'Invoice: .+')
        with self.assertRaises(ValueError):m.make_plan([],r'(A)(B)')

    def test_file_cap_refuses_partial_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for i in range(3):(d/f'{i}.tif').write_bytes(b'fictional')
            with self.assertRaises(ValueError):m.discover(d,False,2)

    def test_manifest_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'manifest.csv'
            m.write_manifest(path,[m.Decision(Path('src.tif'),None,'skipped','pattern_not_found')])
            before=path.read_bytes()
            with self.assertRaises(FileExistsError):m.write_manifest(path,[])
            self.assertEqual(before,path.read_bytes())

    def test_existing_manifest_blocks_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);src=d/'source.tif';src.write_bytes(b'fictional')
            manifest=d/'existing.csv';manifest.write_text('historical')
            with patch.object(m,'extract_text',return_value='Invoice: ABC-12'):
                code=m.main([str(d),'--pattern',r'Invoice:\s+(\S+)','--apply','--manifest',str(manifest)])
            self.assertEqual(code,2)
            self.assertTrue(src.exists())
            self.assertFalse((d/'ABC-12.tif').exists())
            self.assertEqual(manifest.read_text(),'historical')

    def test_apply_requires_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source.tif';src.write_bytes(b'fictional')
            with self.assertRaises(SystemExit):
                m.main([str(tmp),'--pattern',r'Invoice:\s+(\S+)','--apply'])
            self.assertTrue(src.exists())

    def test_apply_reserves_durable_audit_before_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);src=d/'source.tif';src.write_bytes(b'fictional')
            audit=d/'audit.csv'
            original=m.apply_plan
            def check_audit_before_mutation(plan):
                self.assertTrue(audit.is_file())
                self.assertIn('planned',audit.read_text())
                self.assertTrue(src.exists())
                return original(plan)
            with patch.object(m,'extract_text',return_value='Invoice: ABC-12'):
                with patch.object(m,'apply_plan',side_effect=check_audit_before_mutation):
                    code=m.main([str(d),'--pattern',r'Invoice:\s+(\S+)','--apply','--manifest',str(audit)])
            self.assertEqual(code,0)
            self.assertFalse(src.exists())
            self.assertTrue((d/'ABC-12.tif').exists())
            self.assertIn('result',audit.read_text())

    def test_atomic_exclusive_link_failure_keeps_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);src=d/'source.tif';src.write_bytes(b'fictional')
            with patch.object(m,'extract_text',return_value='Invoice: ABC-12'):
                plan=m.make_plan([src],r'Invoice:\s+(\S+)')
            with patch.object(m.os,'link',side_effect=FileExistsError('concurrent creation')):
                result=m.apply_plan(plan)
            self.assertEqual(result[0].status,'blocked')
            self.assertTrue(src.exists())
            self.assertFalse((d/'ABC-12.tif').exists())


    def test_psm_default_and_opt_in_commands(self):
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='INVOICE: TEST-19')) as run:
            self.assertIn('TEST-19', m.extract_text(Path('fictional.tif')))
            self.assertEqual(run.call_args.args[0][-2:], ['--psm', '3'])
            m.extract_text(Path('fictional.tif'), page_segmentation=6)
            self.assertEqual(run.call_args.args[0][-2:], ['--psm', '6'])

    def test_invalid_psm_fails_closed_before_ocr_or_rename(self):
        with self.assertRaisesRegex(ValueError, 'unsupported_page_segmentation'):
            m.make_plan([], r'(X)', page_segmentation=4)
        with self.assertRaisesRegex(ValueError, 'unsupported_page_segmentation'):
            m.extract_text(Path('fictional.tif'), page_segmentation=True)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'original.tif';source.write_bytes(b'fictional')
            with self.assertRaises(SystemExit):
                m.main([tmp, '--pattern', r'INVOICE:\s+([A-Z0-9-]+)', '--ocr-psm', '4'])
            self.assertTrue(source.exists())

    def test_opt_in_mode_remains_review_only_without_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'original.tif';source.write_bytes(b'fictional')
            with patch.object(m, 'extract_text', return_value='INVOICE: TEST-19') as ocr:
                self.assertEqual(m.main([tmp, '--pattern', r'INVOICE:\s+([A-Z0-9-]+)', '--ocr-psm','6']), 0)
                self.assertEqual(ocr.call_args.kwargs['page_segmentation'], 6)
            self.assertTrue(source.exists())
            self.assertFalse((Path(tmp)/'TEST-19.tif').exists())

if __name__=='__main__':unittest.main()
