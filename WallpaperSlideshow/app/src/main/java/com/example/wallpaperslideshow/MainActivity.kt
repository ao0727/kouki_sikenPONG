package com.example.wallpaperslideshow

import android.content.SharedPreferences
import android.os.Bundle
import android.text.format.DateFormat
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.ItemTouchHelper
import androidx.recyclerview.widget.RecyclerView
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.example.wallpaperslideshow.databinding.ActivityMainBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.launch
import java.util.Date

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: SlideshowPrefs
    private lateinit var store: ImageStore
    private lateinit var adapter: ImageAdapter

    private var nextRunAt: Long? = null

    /** 写真選択(複数可)。画像のみ */
    private val pickImages =
        registerForActivityResult(ActivityResultContracts.PickMultipleVisualMedia()) { uris ->
            if (uris.isEmpty()) return@registerForActivityResult
            lifecycleScope.launch {
                val added = store.import(uris)
                prefs.images = prefs.images + added
                refreshImages()
                toast(getString(R.string.added_images, added.size))
            }
        }

    /** ワーカーが壁紙を切り替えたら画面の表示も更新する */
    private val prefsListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        when (key) {
            SlideshowPrefs.KEY_CURRENT,
            SlideshowPrefs.KEY_LAST_CHANGED,
            SlideshowPrefs.KEY_RUNNING -> runOnUiThread { updateStatus() }
            SlideshowPrefs.KEY_IMAGES -> runOnUiThread {
                if (adapter.currentItems != prefs.images) refreshImages()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = SlideshowPrefs(this)
        store = ImageStore(this)

        setupImageList()
        setupIntervalSpinner()
        setupSwitches()
        setupButtons()

        WorkManager.getInstance(this)
            .getWorkInfosForUniqueWorkLiveData(SlideshowScheduler.PERIODIC_WORK)
            .observe(this) { infos ->
                val info = infos.firstOrNull { it.state == WorkInfo.State.ENQUEUED || it.state == WorkInfo.State.RUNNING }
                nextRunAt = info?.nextScheduleTimeMillis?.takeIf { it != Long.MAX_VALUE }
                updateStatus()
            }

        refreshImages()

        // 一覧から外れた画像ファイルを掃除
        lifecycleScope.launch { store.deleteOrphans(prefs.images) }
    }

    override fun onStart() {
        super.onStart()
        prefs.prefs.registerOnSharedPreferenceChangeListener(prefsListener)
        refreshImages()
    }

    override fun onStop() {
        prefs.prefs.unregisterOnSharedPreferenceChangeListener(prefsListener)
        super.onStop()
    }

    private fun setupImageList() {
        adapter = ImageAdapter(store, lifecycleScope) { name -> removeImage(name) }
        binding.imageList.layoutManager = GridLayoutManager(this, 3)
        binding.imageList.adapter = adapter

        // 長押しドラッグで並び替え
        val touchHelper = ItemTouchHelper(object : ItemTouchHelper.SimpleCallback(
            ItemTouchHelper.UP or ItemTouchHelper.DOWN or ItemTouchHelper.LEFT or ItemTouchHelper.RIGHT,
            0
        ) {
            override fun onMove(
                recyclerView: RecyclerView,
                viewHolder: RecyclerView.ViewHolder,
                target: RecyclerView.ViewHolder
            ): Boolean {
                adapter.move(viewHolder.bindingAdapterPosition, target.bindingAdapterPosition)
                return true
            }

            override fun onSwiped(viewHolder: RecyclerView.ViewHolder, direction: Int) = Unit

            override fun clearView(recyclerView: RecyclerView, viewHolder: RecyclerView.ViewHolder) {
                super.clearView(recyclerView, viewHolder)
                prefs.images = adapter.currentItems
                adapter.refreshPositions()
            }
        })
        touchHelper.attachToRecyclerView(binding.imageList)
    }

    private fun setupIntervalSpinner() {
        val options = IntervalOption.entries
        binding.intervalSpinner.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            options.map { it.label }
        )
        binding.intervalSpinner.setSelection(options.indexOf(IntervalOption.fromMinutes(prefs.intervalMinutes)))
        binding.intervalSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val minutes = options[position].minutes
                if (minutes == prefs.intervalMinutes) return
                prefs.intervalMinutes = minutes
                SlideshowScheduler.reschedule(this@MainActivity)
                updateStatus()
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
    }

    private fun setupSwitches() {
        binding.shuffleSwitch.isChecked = prefs.shuffle
        binding.shuffleSwitch.setOnCheckedChangeListener { _, checked -> prefs.shuffle = checked }

        binding.lockSwitch.isChecked = prefs.applyToLockScreen
        binding.lockSwitch.setOnCheckedChangeListener { _, checked -> prefs.applyToLockScreen = checked }
    }

    private fun setupButtons() {
        binding.addButton.setOnClickListener {
            pickImages.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        }

        binding.clearButton.setOnClickListener {
            if (prefs.images.isEmpty()) return@setOnClickListener
            MaterialAlertDialogBuilder(this)
                .setTitle(R.string.clear_confirm_title)
                .setMessage(R.string.clear_confirm_message)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.delete) { _, _ -> clearImages() }
                .show()
        }

        binding.toggleButton.setOnClickListener {
            if (prefs.isRunning) {
                SlideshowScheduler.stop(this)
                toast(getString(R.string.stopped))
            } else {
                if (prefs.images.isEmpty()) {
                    toast(getString(R.string.need_images))
                    return@setOnClickListener
                }
                SlideshowScheduler.start(this)
                toast(getString(R.string.started))
            }
            updateStatus()
        }

        binding.nextButton.setOnClickListener {
            if (prefs.images.isEmpty()) {
                toast(getString(R.string.need_images))
                return@setOnClickListener
            }
            SlideshowScheduler.changeNow(this)
            // 手動で切り替えたら、次の自動切り替えもそこから数え直す
            SlideshowScheduler.reschedule(this)
        }
    }

    private fun removeImage(name: String) {
        prefs.images = prefs.images - name
        if (prefs.currentImage == name) prefs.currentImage = null
        lifecycleScope.launch { store.delete(listOf(name)) }
        refreshImages()
        if (prefs.images.isEmpty()) SlideshowScheduler.stop(this)
    }

    private fun clearImages() {
        val names = prefs.images
        SlideshowScheduler.stop(this)
        prefs.images = emptyList()
        prefs.currentImage = null
        prefs.shuffleQueue = emptyList()
        lifecycleScope.launch { store.delete(names) }
        refreshImages()
    }

    private fun refreshImages() {
        val images = prefs.images
        adapter.submit(images)
        adapter.setCurrent(prefs.currentImage)
        binding.imagesHeader.text = getString(R.string.images_header, images.size)
        binding.emptyText.visibility = if (images.isEmpty()) View.VISIBLE else View.GONE
        updateStatus()
    }

    private fun updateStatus() {
        val running = prefs.isRunning
        binding.toggleButton.setText(if (running) R.string.stop else R.string.start)

        val lines = mutableListOf<String>()
        lines += if (running) {
            getString(R.string.status_running, IntervalOption.fromMinutes(prefs.intervalMinutes).label)
        } else {
            getString(R.string.status_stopped)
        }
        val next = nextRunAt
        if (running && next != null) lines += getString(R.string.status_next, formatTime(next))
        val last = prefs.lastChangedAt
        if (last > 0) lines += getString(R.string.status_last, formatTime(last))
        binding.statusText.text = lines.joinToString("\n")

        adapter.setCurrent(prefs.currentImage)
    }

    private fun formatTime(millis: Long): String =
        DateFormat.format("M/d HH:mm", Date(millis)).toString()

    private fun toast(message: String) =
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
}
