#include "Title.h"
#include "DxLib.h"

GameState Title::Update() {
    DrawString(200, 200, "PONG GAME", GetColor(255, 255, 255));
    DrawString(200, 300, "Press Enter to Start", GetColor(255, 255, 255));
    DrawString(200, 350, "Press E to Exit", GetColor(255, 255, 255));

    if (CheckHitKey(KEY_INPUT_RETURN)) {
        return PLAYING; // EnterÇ≈ÉQÅ[ÉÄäJén
    }
   
}
