import numpy as np
import pytest
from t1d_lab.but_ppg import read_but_raw

def fixture(tmp_path,legacy=False):
    shape=(1,300) if legacy else (300,3)
    x=np.arange(np.prod(shape),dtype=np.int16).reshape(shape)-200
    x.flat[0]=-32768
    (tmp_path/'test.dat').write_bytes(x.astype('<i2').tobytes())
    head=f'test {shape[1]} 30 {shape[0]}\n'
    head+='\n'.join(f'test.dat 16 {-2 if i%2==0 else 4}(10)/a.u. 0 0 0 0 0 C{i}' for i in range(shape[1]))
    p=tmp_path/'test.hea';p.write_text(head)
    return p,x

@pytest.mark.parametrize('legacy',[False,True])
def test_preserves_layout_interleaving_signed_gain_and_missing(tmp_path,legacy):
    p,x=fixture(tmp_path,legacy);result=read_but_raw(p)
    np.testing.assert_array_equal(result['digital'],x)
    expected=np.empty(x.shape)
    for row in range(x.shape[0]):
        for col in range(x.shape[1]):
            expected[row,col]=np.nan if x[row,col]==-32768 else (int(x[row,col])-10)/(-2 if col%2==0 else 4)
    np.testing.assert_allclose(result['physical'],expected,rtol=0,atol=0,equal_nan=True)
    assert result['layout']==('legacy_header' if legacy else 'rgb_time_series')

def test_rejects_truncated_data(tmp_path):
    p,_=fixture(tmp_path);(tmp_path/'test.dat').write_bytes(b'\x00\x00')
    with pytest.raises(ValueError,match='length'):read_but_raw(p)

@pytest.mark.parametrize('replacement',['16:1','16x2','16+2','212'])
def test_rejects_unimplemented_wfdb_formats(tmp_path,replacement):
    p,_=fixture(tmp_path);p.write_text(p.read_text().replace(' 16 ',f' {replacement} ',1))
    with pytest.raises(ValueError,match='format'):read_but_raw(p)
