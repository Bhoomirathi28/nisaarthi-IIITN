package in.nisaarthi.app;

import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.view.WindowManager;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    /** Set when the app is opened by an SOS notification, so it shows over the lock screen. */
    public static final String EXTRA_SOS = "nisaarthi_sos";

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(ShakeSosPlugin.class);
        super.onCreate(savedInstanceState);
        showOverLockScreenIfSos(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        showOverLockScreenIfSos(intent);
    }

    private void showOverLockScreenIfSos(Intent intent) {
        boolean sos = intent != null && intent.getBooleanExtra(EXTRA_SOS, false);
        // Only for SOS: normally the app stays behind the lock screen like any other app
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(sos);
            setTurnScreenOn(sos);
        } else if (sos) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                    | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON);
        }
    }
}
