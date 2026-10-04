package org.meshcrap.survey;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ScrollView;

/** Keeps the visible section in place when live readings reflow above it. */
final class StableScrollView extends ScrollView {
    private boolean preserve;
    StableScrollView(Context context) { super(context); }
    void preserveNextLayout() { preserve = true; }

    @Override protected void onLayout(boolean changed, int l, int t, int r, int b) {
        View anchor = null;
        int offset = 0;
        // Capture immediately before layout, not when an update was queued: the
        // reader may have scrolled or flung the page in the meantime.
        if (preserve && getChildCount() > 0 && getChildAt(0) instanceof ViewGroup) {
            ViewGroup content = (ViewGroup)getChildAt(0);
            for (int i = 0; i < content.getChildCount(); i++) {
                View child = content.getChildAt(i);
                if (child.getVisibility() != GONE && child.getBottom() > getScrollY()) {
                    anchor = child;
                    offset = getScrollY() - child.getTop();
                    break;
                }
            }
        }
        preserve = false;
        super.onLayout(changed, l, t, r, b);
        if (anchor != null && anchor.getVisibility() != GONE)
            scrollTo(getScrollX(), anchor.getTop() + offset);
    }
}
