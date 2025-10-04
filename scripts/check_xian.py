import importlib
import pkgutil

mods = [m.name for m in pkgutil.iter_modules() if m.name.startswith('xian')]
print('mods', mods)

try:
    import xian_py as xian
    print('xian_py package ok:', [k for k in dir(xian) if not k.startswith('_')])
except Exception as e:
    print('xian_py import error:', e)

for name in [
    'xian_py.wallet',
    'xian_py.keys',
    'xian_py.crypto',
    'xian_py.mnemonic',
]:
    try:
        m = importlib.import_module(name)
        print(name, '->', [k for k in dir(m) if not k.startswith('_')][:20])
    except Exception as e:
        print(name, 'error:', e)
