package com.midas.client

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.viewmodel.compose.viewModel
import com.midas.client.ui.screen.MainScreen
import com.midas.client.ui.screen.MainViewModel
import com.midas.client.ui.theme.MidasTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MidasTheme {
                val vm: MainViewModel = viewModel()
                MainScreen(viewModel = vm)
            }
        }
    }
}
