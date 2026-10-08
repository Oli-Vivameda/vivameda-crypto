import unittest
import install_factual_guard as i
class ReadyTests(unittest.TestCase):
 def test_retries_read_only_health(self):
  class H:
   calls=0
   def gateway(self,code,timeout):
    self.calls+=1
    assert 'enqueue' not in code
    if self.calls<3:raise ConnectionError()
  h=H();i.wait_runtime(h,pause=lambda _:None);self.assertEqual(h.calls,3)
 def test_timeout_fails_closed(self):
  class H:
   def gateway(self,*a):raise ConnectionError()
  ticks=iter([0,1]);self.assertRaises(ValueError,i.wait_runtime,H(),timeout=.5,clock=lambda:next(ticks),pause=lambda _:None)
 def test_gateway_script_compiles(self):
  import ast,pathlib
  t=ast.parse(pathlib.Path(i.__file__).read_text())
  for n in ast.walk(t):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='gateway' and n.args and isinstance(n.args[0],ast.Constant):compile(n.args[0].value,'gateway','exec')
if __name__=='__main__':unittest.main()
