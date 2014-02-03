import unittest
import gaia_uplift.branch_logic as subject
import util as u

subject.branches = ['v1', 'v2', 'v3']
subject.status_flags = {
    'v1': 'v1-status',
    'v2': 'v2-status',
    'v3': 'v3-status'
}
subject.blocking_flag = 'blocking'
subject.blocking_rules = {
    'v1': ['v1', 'v2', 'v3'],
    'v2': ['v2', 'v3'],
    'v3': ['v3']
}
subject.patch_rules = {
    'approval-v1': ['v1', 'v2', 'v3'],
    'approval-v2': ['v2', 'v3'],
    'approval-v3': ['v3']
}

class TestFlagsToSet(unittest.TestCase):
    def test_no_flags(self):
        flags = subject.flags_to_set([])
        self.assertEqual(flags, {})

    def test_one_flag(self):
        flags = subject.flags_to_set(['v3'])
        self.assertEqual(flags, {'v3-status': 'fixed'})

    def test_two_flags(self):
        flags = subject.flags_to_set(['v2', 'v3'])
        self.assertEqual(flags, {'v3-status': 'fixed',
                                 'v2-status': 'fixed'})


class TestFixedOnBranches(unittest.TestCase):
    def test_fixed_on_no_branches_blocking(self):
        bug = u.make_bug({'blocking': 'v2'})
        fixed_on = subject.fixed_on_branches(bug)
        self.assertEqual([], fixed_on)

    def test_fixed_on_all_branches_blocking(self):
        bug = u.make_bug({'v2-status': 'fixed',
                          'v3-status': 'verified'})
        fixed_on = subject.fixed_on_branches(bug)
        self.assertEqual(['v2', 'v3'], fixed_on)

    def test_fixed_on_one_branch_blocking(self):
        bug = u.make_bug({'v3-status': 'verified'})
        fixed_on = subject.fixed_on_branches(bug)
        self.assertEqual(['v3'], fixed_on)


class TestNeededOnBranches(unittest.TestCase):
    def test_needed_on_blocking_already_fixed(self):
        bug = u.make_bug({'blocking': 'v2',
                          'v2-status': 'fixed',
                          'v3-status': 'verified'})
        needed_on = subject.needed_on_branches(bug)
        self.assertEqual([], needed_on)

    def test_needed_on_blocking_partially_fixed(self):
        bug = u.make_bug({'blocking': 'v2',
                          'v3-status': 'verified'})
        needed_on = subject.needed_on_branches(bug)
        self.assertEqual(['v2'], needed_on)

    def test_needed_on_blocking_partially_fixed(self):
        bug = u.make_bug({'blocking': 'v2'})
        needed_on = subject.needed_on_branches(bug)
        self.assertEqual(['v2', 'v3'], needed_on)

    def test_needed_on_all_branches_patch(self):
        bug = u.make_bug()
        a = u.make_attachment()
        a['flags'] = [u.make_attachment_flag({
            'name': 'approval-v2',
            'status': '+'
        })]
        bug['attachments'] = [a]
        print bug
        needed_on = subject.needed_on_branches(bug)
        self.assertEqual(['v2', 'v3'], needed_on)

    def test_needed_on_some_branches_patch(self):
        bug = u.make_bug({'v2-status': 'fixed'})
        a = u.make_attachment()
        a['flags'] = [u.make_attachment_flag({
            'name': 'approval-v2',
            'status': '+'
        })]
        bug['attachments'] = [a]
        print bug
        needed_on = subject.needed_on_branches(bug)
        self.assertEqual(['v3'], needed_on)
