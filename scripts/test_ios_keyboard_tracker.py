"""Run the project keyboard tracker against UIKit in an already booted simulator.

python scripts/test_ios_keyboard_tracker.py --simulator <simulator-UUID>
This checks native offset locking, not physical keyboard animation or app startup.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
HARNESS = r"""int main(){@autoreleasepool {
 WKWebView *first=[[WKWebView alloc] initWithFrame:CGRectMake(0,0,393,852)];
 first.scrollView.contentSize=CGSizeMake(393,1600);
 WZKeyboardTracker *tracker=[WZKeyboardTracker sharedTracker];tracker.webView=first;
 tracker.tableLocked=YES;
 first.scrollView.contentOffset=CGPointMake(0,128);
 NSCAssert(CGPointEqualToPoint(first.scrollView.contentOffset,CGPointZero),@"Table focus pan must be blocked");
 tracker.tableLocked=NO;first.scrollView.contentOffset=CGPointMake(0,128);
 NSCAssert(first.scrollView.contentOffset.y==128,@"Hall must remain scrollable");
 tracker.tableLocked=YES;
 NSCAssert(first.scrollView.contentOffset.y==0,@"Lock transition must clear previous pan");
 WKWebView *second=[[WKWebView alloc] initWithFrame:CGRectMake(0,0,393,852)];second.scrollView.contentSize=CGSizeMake(393,1600);tracker.webView=second;
 first.scrollView.contentOffset=CGPointMake(0,128);
 NSCAssert(first.scrollView.contentOffset.y==128,@"Old WebView observer must detach");
 second.scrollView.contentOffset=CGPointMake(0,64);
 NSCAssert(second.scrollView.contentOffset.y==0,@"New WebView observer must attach");
 tracker.webView=nil;
 puts("PASS: table offset frozen; hall offset allowed; observer lifecycle preserved");
 }return 0;}
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', required=True)
    args = parser.parse_args()
    source = (ROOT / 'weizhuo/mobile/ios/voice/WZOfflineSpeaker.mm').read_text()
    start = source.index('@interface WZKeyboardTracker')
    end = source.index('@interface WZSystemSpeaker', start)
    actual = '#import <Foundation/Foundation.h>\n#import <UIKit/UIKit.h>\n#import <WebKit/WebKit.h>\n' + source[start:end]
    sdk = subprocess.check_output(['xcrun', '--sdk', 'iphonesimulator', '--show-sdk-path'], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='weizhuo-keyboard-tracker-') as directory:
        path = Path(directory)
        (path / 'test.m').write_text(actual + HARNESS)
        subprocess.run(['xcrun', '--sdk', 'iphonesimulator', 'clang', '-target',
            'arm64-apple-ios16.0-simulator', '-isysroot', sdk, '-fobjc-arc',
            '-framework', 'Foundation', '-framework', 'UIKit', '-framework', 'WebKit',
            '-framework', 'CoreGraphics', str(path / 'test.m'), '-o', str(path / 'test')], check=True)
        subprocess.run(['xcrun', 'simctl', 'spawn', args.simulator, str(path / 'test')], check=True)

if __name__ == '__main__':
    main()
