#include "Game.h"
#include "Paddle.h"
#include "Ball.h"
#include "Score.h"

// パドルをインスタンス
Paddle playerPaddle(50, 200);  // プレイヤーのパドル 
Paddle cpuPaddle(550, 200);    // CPUのパドル 
Score score;                   // スコア
Ball ball(300, 240, score);    // ボールと Score 

Game::Game() {
   
}

GameState Game::Update() {
    // プレイヤーのパドルの操作
    playerPaddle.Update(KEY_INPUT_W, KEY_INPUT_S);

    // CPUのパドルの操作（AI）
    cpuPaddle.AIControl(ball);

    // ボールの更新
    ball.Update();

    // ボールとパドルの衝突処理
    ball.CheckCollision(playerPaddle, cpuPaddle);

    // ボールの描画
    ball.Draw();

    // パドルの描画
    playerPaddle.Draw();
    cpuPaddle.Draw();

    // スコアの描画
    score.Draw();

    // ゲームオーバー判定
    if (score.IsGameOver()) {
        return GAME_OVER;  // ゲームオーバーになったらGAME_OVERに遷移
    }

    return PLAYING;  // ゲームを続ける
}

void Game::Reset() {
    // ゲームをリセットする処理を追加
    playerPaddle = Paddle(50, 200);  // プレイヤーパドルの位置をリセット
    cpuPaddle = Paddle(550, 200);    // CPUパドルの位置をリセット
    ball.Reset(300, 240);            // ボールの位置をリセット
    score.Reset();                   // スコアをリセット
}
