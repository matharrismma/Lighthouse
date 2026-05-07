package run.concordance.launcher

import android.app.Application
import android.util.Log

class ConcordanceApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Log.i("Concordance", "Node launcher starting — looking for concordance.local:8000")
    }
}
