/**
 * Live2D Manager - 完整的Live2D Cubism SDK集成
 * 使用Live2D Cubism SDK for Web实现真正的Live2D功能
 */

// 导入Live2D Core
/// <reference path="../core/live2dcubismcore.d.ts" />

// 导入Live2D Framework模块
import { Live2DCubismFramework, Option, LogLevel } from '../framework/src/live2dcubismframework'
import { CubismDefaultParameterId } from '../framework/src/cubismdefaultparameterid'
import { CubismModelSettingJson } from '../framework/src/cubismmodelsettingjson'
import { CubismUserModel } from '../framework/src/model/cubismusermodel'
import { CubismMatrix44 } from '../framework/src/math/cubismmatrix44'
import { CubismViewMatrix } from '../framework/src/math/cubismviewmatrix'
import { CubismRenderer_WebGL } from '../framework/src/rendering/cubismrenderer_webgl'
import { CubismMoc } from '../framework/src/model/cubismmoc'
import { CubismModel } from '../framework/src/model/cubismmodel'
import { CubismMotion } from '../framework/src/motion/cubismmotion'
import { CubismExpressionMotion } from '../framework/src/motion/cubismexpressionmotion'
import { CubismMotionManager } from '../framework/src/motion/cubismmotionmanager'
import { CubismExpressionMotionManager } from '../framework/src/motion/cubismexpressionmotionmanager'
import { CubismEyeBlink } from '../framework/src/effect/cubismeyeblink'
import { CubismBreath } from '../framework/src/effect/cubismbreath'
import { CubismPose } from '../framework/src/effect/cubismpose'
import { CubismPhysics } from '../framework/src/physics/cubismphysics'
import { CubismTargetPoint } from '../framework/src/math/cubismtargetpoint'
import { csmVector } from '../framework/src/type/csmvector'
import { csmString } from '../framework/src/type/csmstring'
import { csmMap } from '../framework/src/type/csmmap'
import { CubismId } from '../framework/src/id/cubismid'

/**
 * Live2D模型类
 */
class Live2DModel extends CubismUserModel {
  constructor(manager) {
    super()
    
    this._manager = manager
    this._modelSetting = null
    this._userTimeSeconds = 0.0
    
    this._eyeBlinkIds = new csmVector()
    this._lipSyncIds = new csmVector()
    
    this._motions = new csmMap()
    this._expressions = new csmMap()
    
    this._hitArea = new csmVector()
    this._userArea = new csmVector()
    
    // 初始化动作和表情管理器
    this._motionManager = new CubismMotionManager()
    this._expressionManager = new CubismExpressionMotionManager()
    
    // 初始化拖拽管理器
    this._dragManager = new CubismTargetPoint()
    this._dragX = 0.0
    this._dragY = 0.0
    
    this._idParamAngleX = Live2DCubismFramework.CubismFramework.getIdManager().getId(CubismDefaultParameterId.ParamAngleX)
    this._idParamAngleY = Live2DCubismFramework.CubismFramework.getIdManager().getId(CubismDefaultParameterId.ParamAngleY)
    this._idParamAngleZ = Live2DCubismFramework.CubismFramework.getIdManager().getId(CubismDefaultParameterId.ParamAngleZ)
    this._idParamBodyAngleX = Live2DCubismFramework.CubismFramework.getIdManager().getId(CubismDefaultParameterId.ParamBodyAngleX)
    this._idParamEyeBallX = Live2DCubismFramework.CubismFramework.getIdManager().getId(CubismDefaultParameterId.ParamEyeBallX)
    this._idParamEyeBallY = Live2DCubismFramework.CubismFramework.getIdManager().getId(CubismDefaultParameterId.ParamEyeBallY)
    
    // 口型同步相关
    this._lipSyncValue = 0.0
    this._lipsync = true // 默认启用口型同步
    
    this._state = LoadStep.LoadAssets
    this._expressionCount = 0
    this._textureCount = 0
    this._motionCount = 0
    this._allMotionCount = 0
    
    // 眨眼和呼吸效果控制开关
    this._eyeBlinkEnabled = true
    this._breathEnabled = true
  }
  
  /**
   * 从model3.json文件加载模型
   */
  async loadAssets(dir, fileName) {
    try {
      this._modelHomeDir = dir
      console.log(`Loading model assets from: ${dir}${fileName}`)
      
      // 加载model3.json
      console.log('Step 1: Loading model3.json...')
      const response = await fetch(dir + fileName)
      if (!response.ok) {
        throw new Error(`Failed to fetch model3.json: ${response.status} ${response.statusText}`)
      }
      
      const arrayBuffer = await response.arrayBuffer()
      console.log(`Model3.json loaded, size: ${arrayBuffer.byteLength} bytes`)
      
      const setting = new CubismModelSettingJson(arrayBuffer, arrayBuffer.byteLength)
      console.log('Model3.json parsed successfully')
      
      // 验证model3.json内容
      const modelFileName = setting.getModelFileName()
      if (!modelFileName || modelFileName === '') {
        throw new Error('Invalid model3.json: missing model file name')
      }
      console.log(`Model file specified: ${modelFileName}`)
      
      console.log('Step 2: Setting up model...')
      await this.setupModelAsync(setting)
      
      if (this._model == null) {
        throw new Error('Model setup failed: _model is null after setupModel')
      }
      console.log('Model setup completed successfully')
      
      console.log('Step 3: Creating and initializing renderer...')
      this.createRenderer()
      console.log('Renderer initialized')
      
      console.log('Step 4: Setting up textures...')
      await this.setupTexturesAsync()
      console.log('Textures setup completed')
      
      console.log('All assets loaded successfully')
      return true
    } catch (error) {
      console.error('Failed to load assets:', error)
      console.error('Error details:', {
        directory: dir,
        fileName: fileName,
        fullPath: dir + fileName,
        error: error.message
      })
      return false
    }
  }
  
  /**
   * 设置模型（异步版本）
   */
  async setupModelAsync(setting) {
    this._updating = true
    this._initialized = false
    
    this._modelSetting = setting
    
    // CubismModel
    if (this._modelSetting.getModelFileName() != '') {
      const modelFileName = this._modelSetting.getModelFileName()
      console.log(`Loading model file: ${modelFileName}`)
      
      try {
        const response = await fetch(this._modelHomeDir + modelFileName)
        if (!response.ok) {
          throw new Error(`Failed to fetch model file: ${response.status} ${response.statusText}`)
        }
        
        const arrayBuffer = await response.arrayBuffer()
        console.log(`Model file loaded, size: ${arrayBuffer.byteLength} bytes`)
        
        this.loadModel(arrayBuffer)
        console.log('Model loaded into CubismUserModel')
      } catch (error) {
        console.error(`Failed to load model file ${modelFileName}:`, error)
        throw error
      }
    } else {
      throw new Error('Model file name is empty in model3.json')
    }
    
    // Expression
    console.log('Step 2.1: Loading expressions...')
    if (this._modelSetting.getExpressionCount() > 0) {
      const count = this._modelSetting.getExpressionCount()
      console.log(`Loading ${count} expressions`)
      
      for (let i = 0; i < count; i++) {
        const name = this._modelSetting.getExpressionName(i)
        const path = this._modelSetting.getExpressionFileName(i)
        
        try {
          const response = await fetch(this._modelHomeDir + path)
          if (!response.ok) {
            console.warn(`Failed to load expression ${name}: ${response.status}`)
            continue
          }
          
          const arrayBuffer = await response.arrayBuffer()
          const motion = this.loadExpression(arrayBuffer, arrayBuffer.byteLength, name)
          
          if (this._expressions.getValue(name) != null) {
            this._expressions.getValue(name).release()
            this._expressions.setValue(name, null)
          }
          
          this._expressions.setValue(name, motion)
          this._expressionCount++
          console.log(`Expression ${name} loaded successfully`)
        } catch (error) {
          console.warn(`Failed to load expression ${name}:`, error)
        }
      }
      
      this._state = LoadStep.LoadPhysics
    } else {
      console.log('No expressions to load')
      this._state = LoadStep.LoadPhysics
    }
    
    // Physics
    console.log('Step 2.2: Loading physics...')
    if (this._modelSetting.getPhysicsFileName() != '') {
      const physicsFileName = this._modelSetting.getPhysicsFileName()
      console.log(`Loading physics file: ${physicsFileName}`)
      
      try {
        const response = await fetch(this._modelHomeDir + physicsFileName)
        if (!response.ok) {
          console.warn(`Failed to load physics: ${response.status}`)
        } else {
          const arrayBuffer = await response.arrayBuffer()
          this.loadPhysics(arrayBuffer, arrayBuffer.byteLength)
          console.log('Physics loaded successfully')
        }
      } catch (error) {
        console.warn('Failed to load physics:', error)
      }
      
      this._state = LoadStep.LoadPose
    } else {
      console.log('No physics file to load')
      this._state = LoadStep.LoadPose
    }
    
    // Pose
    console.log('Step 2.3: Loading pose...')
    if (this._modelSetting.getPoseFileName() != '') {
      const poseFileName = this._modelSetting.getPoseFileName()
      console.log(`Loading pose file: ${poseFileName}`)
      
      try {
        const response = await fetch(this._modelHomeDir + poseFileName)
        if (!response.ok) {
          console.warn(`Failed to load pose: ${response.status}`)
        } else {
          const arrayBuffer = await response.arrayBuffer()
          this.loadPose(arrayBuffer, arrayBuffer.byteLength)
          console.log('Pose loaded successfully')
        }
      } catch (error) {
        console.warn('Failed to load pose:', error)
      }
      
      this._state = LoadStep.SetupEyeBlink
    } else {
      console.log('No pose file to load')
      this._state = LoadStep.SetupEyeBlink
    }
    
    // EyeBlink
    if (this._modelSetting.getEyeBlinkParameterCount() > 0) {
      this._eyeBlink = CubismEyeBlink.create(this._modelSetting)
      this._state = LoadStep.SetupBreath
    }
    
    // Breath
    this._breath = CubismBreath.create()
    const breathParameters = new csmVector()
    breathParameters.pushBack(new BreathParameterData(this._idParamAngleX, 0.0, 15.0, 6.5345, 0.5))
    breathParameters.pushBack(new BreathParameterData(this._idParamAngleY, 0.0, 8.0, 3.5345, 0.5))
    breathParameters.pushBack(new BreathParameterData(this._idParamAngleZ, 0.0, 10.0, 5.5345, 0.5))
    breathParameters.pushBack(new BreathParameterData(this._idParamBodyAngleX, 0.0, 4.0, 15.5345, 0.5))
    this._breath.setParameters(breathParameters)
    this._state = LoadStep.LoadUserData
    
    // UserData
    if (this._modelSetting.getUserDataFile() != '') {
      const userDataFile = this._modelSetting.getUserDataFile()
      
      fetch(this._modelHomeDir + userDataFile)
        .then(response => response.arrayBuffer())
        .then(arrayBuffer => {
          this.loadUserData(arrayBuffer, arrayBuffer.byteLength)
          this._state = LoadStep.SetupEyeBlinkIds
        })
    } else {
      this._state = LoadStep.SetupEyeBlinkIds
    }
    
    // EyeBlinkIds
    const eyeBlinkIdCount = this._modelSetting.getEyeBlinkParameterCount()
    for (let i = 0; i < eyeBlinkIdCount; ++i) {
      this._eyeBlinkIds.pushBack(this._modelSetting.getEyeBlinkParameterId(i))
    }
    this._state = LoadStep.SetupLipSyncIds
    
    // LipSyncIds
    const lipSyncIdCount = this._modelSetting.getLipSyncParameterCount()
    for (let i = 0; i < lipSyncIdCount; ++i) {
      this._lipSyncIds.pushBack(this._modelSetting.getLipSyncParameterId(i))
    }
    this._state = LoadStep.SetupLayout
    
    // Layout
    const layout = new csmMap()
    this._modelSetting.getLayoutMap(layout)
    this._modelMatrix.setupFromLayout(layout)
    this._state = LoadStep.LoadMotion
    
    // Motion
    this._state = LoadStep.WaitLoadMotion
    this._allMotionCount = 0
    this._motionCount = 0
    const allMotionCount = this._modelSetting.getMotionGroupCount()
    
    // モーションの総数を求める
    for (let i = 0; i < allMotionCount; i++) {
      const group = this._modelSetting.getMotionGroupName(i)
      this._allMotionCount += this._modelSetting.getMotionCount(group)
    }
    
    // モーションの読み込み
    for (let i = 0; i < allMotionCount; i++) {
      this.preLoadMotionGroup(this._modelSetting.getMotionGroupName(i))
    }
    
    // モーションがない場合
    if (allMotionCount == 0) {
      this._state = LoadStep.LoadTexture
      console.log('No motions to load, proceeding to texture loading')
    } else {
      console.log(`Loading ${this._allMotionCount} motions in ${allMotionCount} groups`)
    }
    
    // 设置状态为纹理加载，无论是否有动作
    this._state = LoadStep.LoadTexture
    console.log('Model setup completed, ready for texture loading')
    
    this._updating = false
    this._initialized = true
  }
  
  /**
   * 设置纹理（异步版本）
   */
  async setupTexturesAsync() {
    const usePremultiply = true
    
    if (this._state == LoadStep.LoadTexture) {
      // 纹理加载
      const textureCount = this._modelSetting.getTextureCount()
      console.log(`Loading ${textureCount} textures...`)
      
      for (let modelTextureNumber = 0; modelTextureNumber < textureCount; modelTextureNumber++) {
        // 纹理名为空时跳过加载和绑定处理
        if (this._modelSetting.getTextureFileName(modelTextureNumber) == '') {
          console.log('getTextureFileName null')
          continue
        }
        
        // WebGLのテクスチャユニットにテクスチャをロードする
        let texturePath = this._modelSetting.getTextureFileName(modelTextureNumber)
        texturePath = this._modelHomeDir + texturePath
        
        console.log(`Loading texture ${modelTextureNumber}: ${texturePath}`)
        
        try {
          // 验证纹理文件是否存在
          const testResponse = await fetch(texturePath)
          if (!testResponse.ok) {
            throw new Error(`Texture file not found: ${texturePath} (Status: ${testResponse.status})`)
          }
          
          // 创建纹理对象
          const texture = await this.createTextureFromPath(texturePath, usePremultiply, this._manager.gl)
          
          if (texture) {
            this.getRenderer().bindTexture(modelTextureNumber, texture)
            this._textureCount++
            console.log(`Texture ${modelTextureNumber} loaded successfully`)
          } else {
            throw new Error(`Failed to create texture from ${texturePath}`)
          }
        } catch (error) {
          console.error(`Failed to load texture ${modelTextureNumber}:`, error)
          throw error
        }
      }
      
      // 启动渲染器
      this.getRenderer().startUp(this._manager.gl)
      
      this._state = LoadStep.CompleteSetup
      console.log(`All ${this._textureCount} textures loaded successfully`)
      console.log('Renderer started up successfully')
    }
  }
  
  /**
   * 从路径创建纹理
   */
  async createTextureFromPath(texturePath, usePremultiply, gl) {
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      
      img.onload = () => {
        try {
          // 创建WebGL纹理
          // gl 参数已经传入
          const texture = gl.createTexture()
          
          gl.bindTexture(gl.TEXTURE_2D, texture)
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR)
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
          
          // Premultiplied alpha处理
          if (usePremultiply) {
            gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 1)
          }
          
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img)
          gl.generateMipmap(gl.TEXTURE_2D)
          
          resolve(texture)
        } catch (error) {
          console.error('Failed to create WebGL texture:', error)
          reject(error)
        }
      }
      
      img.onerror = () => {
        reject(new Error(`Failed to load image: ${texturePath}`))
      }
      
      img.src = texturePath
    })
  }
  
  /**
   * 更新模型
   * @param {number} deltaTimeSeconds - 时间增量（秒）
   */
  update(deltaTimeSeconds = 0.016) {
    if (this._state != LoadStep.CompleteSetup) {
      return
    }
    
    this._userTimeSeconds += deltaTimeSeconds
    
    this._dragManager.update(deltaTimeSeconds)
    this._dragX = this._dragManager.getX()
    this._dragY = this._dragManager.getY()
    
    // モーションによるパラメータ更新の有無
    let motionUpdated = false
    
    // 前回セーブされた状態をロード
    this._model.loadParameters()
    
    // モーションの更新
    if (this._motionManager.isFinished()) {
      // モーションの再生がない場合、待機モーションの中からランダムで再生する
      const idleGroup = this._motions.getValue('Idle')
      if (idleGroup != null && idleGroup.getSize() > 0) {
        this.startRandomMotion('Idle', 3)
      }
    }
    
    // 只有在有动作正在播放时才更新动作
    if (!this._motionManager.isFinished() && this._model != null && this._motionManager != null) {
      try {
        motionUpdated = this._motionManager.updateMotion(this._model, deltaTimeSeconds)
      } catch (error) {
        console.error('Error updating motion:', error)
        // 如果更新动作时出错，停止当前动作
        this._motionManager.stopAllMotions()
      }
    }
    
    // 状態を保存
    this._model.saveParameters()
    
    // 表情でパラメータ更新（相対変化）
    if (this._expressionManager != null && this._model != null) {
      try {
        this._expressionManager.updateMotion(this._model, deltaTimeSeconds)
      } catch (error) {
        console.error('Error updating expression:', error)
      }
    }
    
    // ドラッグによる変化
    // ドラッグによる顔の向きの調整
    this._model.addParameterValueById(this._idParamAngleX, this._dragX * 30) // -30から30の値を加える
    this._model.addParameterValueById(this._idParamAngleY, this._dragY * 30)
    this._model.addParameterValueById(this._idParamAngleZ, this._dragX * this._dragY * -30)
    
    // ドラッグによる体の向きの調整
    this._model.addParameterValueById(this._idParamBodyAngleX, this._dragX * 10) // -10から10の値を加える
    
    // ドラッグによる目の向きの調整
    this._model.addParameterValueById(this._idParamEyeBallX, this._dragX) // -1から1の値を加える
    this._model.addParameterValueById(this._idParamEyeBallY, this._dragY)
    
    // 眨眼效果
    if (this._eyeBlink != null && this._eyeBlinkEnabled === true) {
      this._eyeBlink.updateParameters(this._model, deltaTimeSeconds)
    }
    
    // 呼吸效果
    if (this._breath != null && this._breathEnabled === true) {
      this._breath.updateParameters(this._model, deltaTimeSeconds)
    }
    
    // 物理演算の設定
    if (this._physics != null) {
      this._physics.evaluate(this._model, deltaTimeSeconds)
    }
    
    // リップシンクの設定
    if (this._lipsync && this._lipSyncIds.getSize() > 0) {
      // リアルタイムでリップシンクを行う場合、システムから音量を取得して0〜1の範囲で値を入力します。
      const value = this._lipSyncValue || 0.0 // 使用实际的口型同步值
      
      for (let i = 0; i < this._lipSyncIds.getSize(); ++i) {
        this._model.addParameterValueById(this._lipSyncIds.at(i), value, 0.8)
      }
    }
    
    // ポーズの設定
    if (this._pose != null) {
      this._pose.updateParameters(this._model, deltaTimeSeconds)
    }
    
    this._model.update()
  }
  
  /**
   * 开始随机动作
   * @param {string} group - 动作组名
   * @param {number} priority - 优先级
   */
  startRandomMotion(group, priority) {
    if (this._state != LoadStep.CompleteSetup) {
      return
    }
    
    const count = this._modelSetting.getMotionCount(group)
    if (count === 0) {
      console.warn(`No motions found for group: ${group}`)
      return
    }
    
    const no = Math.floor(Math.random() * count)
    this.startMotion(group, no, priority)
  }

  /**
   * 预加载动作组
   * @param {string} group - 动作组名
   */
  async preLoadMotionGroup(group) {
    const count = this._modelSetting.getMotionCount(group)
    
    for (let i = 0; i < count; i++) {
      const motionFileName = this._modelSetting.getMotionFileName(group, i)
      const motionPath = this._modelHomeDir + motionFileName
      
      // 使用官方示例的命名方式: group_index
      const name = `${group}_${i}`
      
      try {
        const response = await fetch(motionPath)
        if (!response.ok) {
          console.warn(`Failed to load motion ${group}[${i}]: ${response.status}`)
          this._allMotionCount--
          continue
        }
        
        const arrayBuffer = await response.arrayBuffer()
        const motion = this.loadMotion(arrayBuffer, arrayBuffer.byteLength, name)
        
        if (motion) {
          const fadeTime = this._modelSetting.getMotionFadeInTimeValue(group, i)
          if (fadeTime >= 0.0) {
            motion.setFadeInTime(fadeTime)
          }
          
          const fadeOutTime = this._modelSetting.getMotionFadeOutTimeValue(group, i)
          if (fadeOutTime >= 0.0) {
            motion.setFadeOutTime(fadeOutTime)
          }
          
          // 设置眨眼和唇同步效果
          if (this._eyeBlinkIds && this._lipSyncIds) {
            motion.setEffectIds(this._eyeBlinkIds, this._lipSyncIds)
          }
          
          // 删除已存在的同名动作
          if (this._motions.getValue(name) != null) {
            this._motions.getValue(name).delete()
          }
          
          this._motions.setValue(name, motion)
          this._motionCount++
          console.log(`Motion ${name} loaded successfully`)
        } else {
          this._allMotionCount--
        }
      } catch (error) {
        console.warn(`Failed to load motion ${group}[${i}]:`, error)
        this._allMotionCount--
      }
    }
  }

  /**
   * 开始播放动作
   * @param {string} group - 动作组名
   * @param {number} no - 动作编号
   * @param {number} priority - 优先级
   */
  startMotion(group, no, priority) {
    if (this._state != LoadStep.CompleteSetup) {
      return
    }
    
    if (priority == 3) {
      this._motionManager.setReservePriority(priority)
    } else if (!this._motionManager.reserveMotion(priority)) {
      return
    }
    
    // 使用官方示例的命名方式获取动作
    const name = `${group}_${no}`
    const motion = this._motions.getValue(name)
    
    if (!motion) {
      console.warn(`Motion not found: ${name}`)
      return
    }
    
    try {
      this._motionManager.startMotionPriority(motion, false, priority)
      console.log(`Started motion: ${name}`)
    } catch (error) {
      console.error(`Error starting motion ${name}:`, error)
    }
  }
  


  /**
   * 点击测试 - 检测指定坐标是否命中模型的HitArea
   * @param {number} x - 标准化的X坐标 (-1.0 到 1.0)
   * @param {number} y - 标准化的Y坐标 (-1.0 到 1.0)
   * @returns {string|null} - 命中的区域名称，如果没有命中则返回null
   */
  hitTest(x, y) {
    // 透明时不进行点击检测
    if (this.getOpacity() < 1) {
      return null
    }

    if (!this._modelSetting) {
      return null
    }

    const count = this._modelSetting.getHitAreasCount()

    for (let i = 0; i < count; i++) {
      const areaName = this._modelSetting.getHitAreaName(i)
      const drawId = this._modelSetting.getHitAreaId(i)
      
      if (this.isHit(drawId, x, y)) {
        return areaName
      }
    }

    return null
  }

  /**
   * 获取所有可用的HitArea信息
   * @returns {Array} - HitArea信息数组
   */
  getHitAreas() {
    if (!this._modelSetting) {
      return []
    }

    const hitAreas = []
    const count = this._modelSetting.getHitAreasCount()

    for (let i = 0; i < count; i++) {
      const areaName = this._modelSetting.getHitAreaName(i)
      const drawId = this._modelSetting.getHitAreaId(i)
      const drawIndex = this._model.getDrawableIndex(drawId)
      
      if (drawIndex >= 0) {
        // 获取drawable的顶点信息来计算边界
        const vertexCount = this._model.getDrawableVertexCount(drawIndex)
        const vertices = this._model.getDrawableVertices(drawIndex)
        
        let left = vertices[0]
        let right = vertices[0]
        let top = vertices[1]
        let bottom = vertices[1]
        
        for (let j = 1; j < vertexCount; j++) {
          const x = vertices[j * 2]
          const y = vertices[j * 2 + 1]
          
          if (x < left) left = x
          if (x > right) right = x
          if (y < top) top = y
          if (y > bottom) bottom = y
        }
        
        hitAreas.push({
          id: drawId.s || drawId,
          name: areaName,
          drawIndex: drawIndex,
          bounds: {
            left: left,
            right: right,
            top: top,
            bottom: bottom
          },
          vertices: vertices,
          vertexCount: vertexCount
        })
      }
    }

    return hitAreas
  }

  /**
   * 设置自动眨眼开关
   * @param {boolean} enabled - 是否启用自动眨眼
   */
  setAutoEyeBlinkEnable(enabled) {
    this._eyeBlinkEnabled = enabled
    console.log(`Auto eye blink: ${enabled ? 'enabled' : 'disabled'}`)
  }
  
  /**
   * 设置自动呼吸开关
   * @param {boolean} enabled - 是否启用自动呼吸
   */
  setAutoBreathEnable(enabled) {
    this._breathEnabled = enabled
    console.log(`Auto breath: ${enabled ? 'enabled' : 'disabled'}`)
  }
  
  /**
   * 获取自动眨眼状态
   * @returns {boolean} - 自动眨眼是否启用
   */
  getAutoEyeBlinkEnabled() {
    return this._eyeBlinkEnabled
  }
  
  /**
   * 获取自动呼吸状态
   * @returns {boolean} - 自动呼吸是否启用
   */
  getAutoBreathEnabled() {
    return this._breathEnabled
  }

  /**
   * 设置口型同步值
   * @param {number} value - 口型开合值 (0.0 到 1.0)
   */
  setLipSyncValue(value) {
    // 限制值在0.0到1.0之间
    this._lipSyncValue = Math.max(0.0, Math.min(1.0, value))
  }

  /**
   * 获取当前口型同步值
   * @returns {number} - 当前口型同步值
   */
  getLipSyncValue() {
    return this._lipSyncValue || 0.0
  }

  /**
   * 设置口型同步功能开关
   * @param {boolean} enabled - 是否启用口型同步
   */
  setLipSyncEnable(enabled) {
    this._lipsync = enabled
    console.log(`Lip sync ${enabled ? 'enabled' : 'disabled'}`)
  }

  /**
   * 绘制模型
   */
  draw(matrix) {
    if (this._model == null) {
      return
    }
    
    // 各読み込み終了後
    if (this._state == LoadStep.CompleteSetup) {
      // 设置MVP矩阵
      matrix.multiplyByMatrix(this.getModelMatrix())
      this.getRenderer().setMvpMatrix(matrix)
      
      // 设置渲染状态
      const canvas = this._manager.canvas
      const viewport = [0, 0, canvas.width, canvas.height]
      this.getRenderer().setRenderState(null, viewport)
      
      // 不透明度の設定
      this.getRenderer().setIsPremultipliedAlpha(true)
      this.getRenderer().drawModel()
    }
  }
}

/**
 * 加载步骤枚举
 */
const LoadStep = {
  LoadAssets: 0,
  LoadModel: 1,
  WaitLoadModel: 2,
  LoadExpression: 3,
  WaitLoadExpression: 4,
  LoadPhysics: 5,
  WaitLoadPhysics: 6,
  LoadPose: 7,
  WaitLoadPose: 8,
  SetupEyeBlink: 9,
  SetupBreath: 10,
  LoadUserData: 11,
  WaitLoadUserData: 12,
  SetupEyeBlinkIds: 13,
  SetupLipSyncIds: 14,
  SetupLayout: 15,
  LoadMotion: 16,
  WaitLoadMotion: 17,
  LoadTexture: 18,
  WaitLoadTexture: 19,
  CompleteSetup: 20
}

/**
 * 呼吸参数数据类
 */
class BreathParameterData {
  constructor(parameterId, offset, peak, cycle, weight) {
    this.parameterId = parameterId
    this.offset = offset
    this.peak = peak
    this.cycle = cycle
    this.weight = weight
  }
}

/**
 * Live2D管理器主类
 */
class Live2DManager {
  constructor() {
    this.canvas = null
    this.gl = null
    this.isInitialized = false
    this.isModelLoaded = false
    this.currentModel = null
    this.animationId = null
    this.viewMatrix = null
    this.deviceToScreen = null
    this.eyeTrackingEnabled = true // 默认启用眼神跟随
    this.currentScale = 1.0 // 存储当前的缩放值
    
    // 背景相关
    this.backgroundTexture = null
    this.backgroundOpacity = 1.0
    this.backgroundShaderProgram = null
    this.backgroundVertexBuffer = null
    this.backgroundUVBuffer = null
    this.backgroundIndexBuffer = null
  }

  /**
   * 初始化Live2D管理器
   * @param {HTMLCanvasElement} canvas - Canvas元素
   */
  async initialize(canvas) {
    try {
      this.canvas = canvas
      
      // 获取WebGL上下文
      this.gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
      if (!this.gl) {
        throw new Error('WebGL not supported')
      }
      
      // 初始化Live2D Cubism Framework
      const cubismOption = new Option()
      cubismOption.logFunction = console.log
      cubismOption.loggingLevel = LogLevel.LogLevel_Verbose
      
      Live2DCubismFramework.CubismFramework.startUp(cubismOption)
      Live2DCubismFramework.CubismFramework.initialize()
      
      // 设置WebGL基本配置
      this.gl.enable(this.gl.BLEND)
      this.gl.blendFunc(this.gl.SRC_ALPHA, this.gl.ONE_MINUS_SRC_ALPHA)
      // 设置背景色为渐变色的起始色，确保占满整个显示区域
      this.gl.clearColor(0.4, 0.494, 0.918, 1.0) // #667eea 转换为 RGB
      
      // 设置视口以支持高DPI
      this.gl.viewport(0, 0, canvas.width, canvas.height)
      
      // 初始化视图矩阵
      this.viewMatrix = new CubismViewMatrix()
      this.deviceToScreen = new CubismMatrix44()
      this.updateViewMatrix()
      
      // 初始化背景着色器
      this.initializeBackgroundShader()
      
      this.isInitialized = true
      console.log('Live2D Manager initialized successfully')
      
    } catch (error) {
      console.error('Failed to initialize Live2D Manager:', error)
      throw error
    }
  }

  /**
   * 加载Live2D模型
   * @param {string} modelPath - 模型文件路径
   */
  async loadModel(modelPath) {
    try {
      if (!this.isInitialized) {
        throw new Error('Live2D Manager not initialized')
      }
      
      console.log('Loading Live2D model:', modelPath)
      
      // 释放之前的模型
      if (this.currentModel) {
        this.currentModel.release()
        this.currentModel = null
      }
      
      // 创建新模型
      this.currentModel = new Live2DModel(this)
      
      // 解析模型路径
      const pathParts = modelPath.split('/')
      const fileName = pathParts.pop()
      const dir = pathParts.join('/') + '/'
      
      console.log('Model directory:', dir)
      console.log('Model file name:', fileName)
      
      // 验证模型文件是否存在
      try {
        const testResponse = await fetch(modelPath)
        if (!testResponse.ok) {
          throw new Error(`Model file not found: ${modelPath} (Status: ${testResponse.status})`)
        }
        console.log('Model file exists and accessible')
      } catch (fetchError) {
        console.error('Failed to access model file:', fetchError)
        throw new Error(`Cannot access model file: ${modelPath}. Please check if the file exists and the path is correct.`)
      }
      
      // 加载模型
      const success = await this.currentModel.loadAssets(dir, fileName)
      
      if (!success) {
        console.error('loadAssets returned false')
        console.error('Possible causes:')
        console.error('1. Network request failed for model3.json or related files')
        console.error('2. Model loading failed (invalid .moc3 file)')
        console.error('3. Missing texture files or other resources')
        console.error('4. Incorrect file paths in model3.json')
        throw new Error('Failed to load model assets - check console for detailed error information')
      }
      
      this.isModelLoaded = true
      console.log('Live2D model loaded successfully')
      
      // 应用初始缩放值
      this.updateViewMatrix()
      
      return this.currentModel
      
    } catch (error) {
      console.error('Failed to load Live2D model:', error)
      this.isModelLoaded = false
      throw error
    }
  }

  /**
   * 开始渲染循环
   */
  startRendering() {
    if (!this.isInitialized || !this.canvas) {
      console.warn('Cannot start rendering: not initialized')
      return
    }
    
    let lastTime = Date.now()
    
    const render = () => {
      if (this.gl && this.canvas) {
        // 计算deltaTime
        const currentTime = Date.now()
        const deltaTime = (currentTime - lastTime) / 1000.0
        lastTime = currentTime
        
        // 清除画布
        this.gl.viewport(0, 0, this.canvas.width, this.canvas.height)
        this.gl.clear(this.gl.COLOR_BUFFER_BIT)
        
        // 绘制背景（如果有）
        if (this.backgroundTexture) {
          this.drawBackground()
        }
        
        // 如果有模型，更新和绘制
        if (this.isModelLoaded && this.currentModel) {
          // 传递deltaTime给update方法
          this.currentModel.update(deltaTime)
          
          // 计算MVP矩阵
          const mvpMatrix = new CubismMatrix44()
          mvpMatrix.multiplyByMatrix(this.deviceToScreen)
          mvpMatrix.multiplyByMatrix(this.viewMatrix)
          mvpMatrix.multiplyByMatrix(this.currentModel.getModelMatrix())
          
          this.currentModel.draw(mvpMatrix)
        }
      }
      
      this.animationId = requestAnimationFrame(render)
    }
    
    render()
    console.log('Live2D rendering started')
  }

  /**
   * 停止渲染循环
   */
  stopRendering() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId)
      this.animationId = null
      console.log('Live2D rendering stopped')
    }
  }

  /**
   * 播放动作
   * @param {string} group - 动作组名
   * @param {number} no - 动作编号
   * @param {number} priority - 优先级
   */
  startMotion(group, no, priority = 2) {
    if (!this.isModelLoaded || !this.currentModel) {
      console.warn('No model loaded')
      return
    }
    
    this.currentModel.startMotion(group, no, priority)
    console.log(`Playing motion: ${group}_${no} (priority: ${priority})`)
  }

  /**
   * 设置表情
   * @param {string} expressionId - 表情ID
   */
  setExpression(expressionId) {
    if (!this.isModelLoaded || !this.currentModel) {
      console.warn('No model loaded')
      return
    }
    
    this.currentModel.setExpression(expressionId)
    console.log(`Setting expression: ${expressionId}`)
  }

  /**
   * 从文件URL设置表情
   * @param {string} fileUrl - 表情文件的URL
   */
  async setExpressionFromFile(fileUrl) {
    if (!this.isModelLoaded || !this.currentModel) {
      console.warn('No model loaded')
      return
    }
    
    try {
      console.log(`Loading expression from file: ${fileUrl}`)
      
      // 获取文件内容
      const response = await fetch(fileUrl)
      if (!response.ok) {
        throw new Error(`Failed to fetch expression file: ${response.status} ${response.statusText}`)
      }
      
      // 检查响应的Content-Type
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('text/html')) {
        throw new Error('Expression file not found - server returned HTML page instead of expression file')
      }
      
      const arrayBuffer = await response.arrayBuffer()
      
      // 验证文件内容不是HTML
      const textContent = new TextDecoder().decode(arrayBuffer.slice(0, 100))
      if (textContent.includes('<!DOCTYPE') || textContent.includes('<html>')) {
        throw new Error('Expression file not found - received HTML content instead of expression file')
      }
      
      // 验证是否为有效的JSON格式
      try {
        const jsonText = new TextDecoder().decode(arrayBuffer)
        const expressionData = JSON.parse(jsonText)
        
        // 简单验证是否为表情文件
        if (!expressionData.Type || expressionData.Type !== 'Live2D Expression') {
          throw new Error('Invalid expression file format - missing or incorrect Type field')
        }
        if (!expressionData.Parameters || !Array.isArray(expressionData.Parameters)) {
          throw new Error('Invalid expression file format - missing or invalid Parameters field')
        }
      } catch (parseError) {
        throw new Error(`Invalid expression file format: ${parseError.message}`)
      }
      
      // 加载表情
      const motion = this.currentModel.loadExpression(arrayBuffer, arrayBuffer.byteLength, 'custom_expression')
      
      if (motion) {
        // 直接使用表情管理器播放表情
        if (this.currentModel._expressionManager) {
          this.currentModel._expressionManager.startMotion(motion, false)
          console.log('Custom expression loaded and applied successfully')
        } else {
          console.warn('Expression manager not available')
        }
      } else {
        throw new Error('Failed to create expression motion from file - loadExpression returned null')
      }
      
    } catch (error) {
      console.error('Failed to set expression from file:', error)
      throw error
    }
  }

  /**
   * 设置自动眨眼开关
   * @param {boolean} enabled - 是否启用自动眨眼
   */
  setAutoEyeBlinkEnable(enabled) {
    if (!this.isModelLoaded || !this.currentModel) {
      console.warn('No model loaded')
      return
    }
    
    this.currentModel.setAutoEyeBlinkEnable(enabled)
  }
  
  /**
   * 设置自动呼吸开关
   * @param {boolean} enabled - 是否启用自动呼吸
   */
  setAutoBreathEnable(enabled) {
    if (!this.isModelLoaded || !this.currentModel) {
      console.warn('No model loaded')
      return
    }
    
    this.currentModel.setAutoBreathEnable(enabled)
  }
  
  /**
   * 获取自动眨眼状态
   * @returns {boolean} - 自动眨眼是否启用
   */
  getAutoEyeBlinkEnabled() {
    if (!this.isModelLoaded || !this.currentModel) {
      return false
    }
    
    return this.currentModel.getAutoEyeBlinkEnabled()
  }
  
  /**
   * 获取自动呼吸状态
   * @returns {boolean} - 自动呼吸是否启用
   */
  getAutoBreathEnabled() {
    if (!this.isModelLoaded || !this.currentModel) {
      return false
    }
    
    return this.currentModel.getAutoBreathEnabled()
  }

  /**
   * 从文件设置动作
   * @param {string} fileUrl - 动作文件的URL
   */
  async setMotionFromFile(fileUrl) {
    if (!this.isModelLoaded || !this.currentModel) {
      console.warn('No model loaded')
      return
    }
    
    try {
      console.log(`Loading motion from file: ${fileUrl}`)
      
      // 获取文件内容
      const response = await fetch(fileUrl)
      if (!response.ok) {
        throw new Error(`Failed to fetch motion file: ${response.status} ${response.statusText}`)
      }
      
      // 检查响应的Content-Type
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('text/html')) {
        throw new Error('Motion file not found - server returned HTML page instead of motion file')
      }
      
      const arrayBuffer = await response.arrayBuffer()
      
      // 验证文件内容不是HTML
      const textContent = new TextDecoder().decode(arrayBuffer.slice(0, 100))
      if (textContent.includes('<!DOCTYPE') || textContent.includes('<html>')) {
        throw new Error('Motion file not found - received HTML content instead of motion file')
      }
      
      // 验证是否为有效的JSON格式
      try {
        const jsonText = new TextDecoder().decode(arrayBuffer)
        const motionData = JSON.parse(jsonText)
        
        // 简单验证是否为动作文件
        if (!motionData.Version || !motionData.Meta) {
          throw new Error('Invalid motion file format - missing Version or Meta fields')
        }
      } catch (parseError) {
        throw new Error(`Invalid motion file format: ${parseError.message}`)
      }
      
      // 使用CubismMotion.create创建动作
      const motion = CubismMotion.create(arrayBuffer, arrayBuffer.byteLength)
      
      if (motion) {
        // 设置淡入淡出时间
        motion.setFadeInTime(1.0)
        motion.setFadeOutTime(1.0)
        
        // 设置眨眼和唇同步效果
        if (this.currentModel._eyeBlinkIds && this.currentModel._lipSyncIds) {
          motion.setEffectIds(this.currentModel._eyeBlinkIds, this.currentModel._lipSyncIds)
        }
        
        // 使用动作管理器播放动作
        if (this.currentModel._motionManager) {
          this.currentModel._motionManager.startMotionPriority(motion, false, 3)
          console.log('Custom motion loaded and started successfully')
        } else {
          console.warn('Motion manager not available')
        }
      } else {
        throw new Error('Failed to create motion from file - CubismMotion.create returned null')
      }
      
    } catch (error) {
      console.error('Failed to set motion from file:', error)
      throw error
    }
  }

  /**
   * 处理指针移动
   * @param {number} x - X坐标 (相对于canvas的像素坐标)
   * @param {number} y - Y坐标 (相对于canvas的像素坐标)
   */
  onPointerMove(x, y) {
    if (!this.isModelLoaded || !this.currentModel || !this.eyeTrackingEnabled) return
    
    // 获取canvas的显示尺寸
    const canvasWidth = this.canvas.clientWidth
    const canvasHeight = this.canvas.clientHeight
    
    // 转换坐标到模型空间 (-1.0 到 1.0)
    const normalizedX = (x / canvasWidth) * 2.0 - 1.0
    const normalizedY = -((y / canvasHeight) * 2.0 - 1.0)
    
    // 设置拖拽参数
    this.currentModel.setDragging(normalizedX, normalizedY)
  }

  /**
   * 处理点击事件
   * @param {number} x - X坐标 (相对于canvas的像素坐标)
   * @param {number} y - Y坐标 (相对于canvas的像素坐标)
   */
  onTap(x, y) {
    if (!this.isModelLoaded || !this.currentModel) return
    
    // 获取canvas的显示尺寸
    const canvasWidth = this.canvas.clientWidth
    const canvasHeight = this.canvas.clientHeight
    
    // 转换坐标到模型空间 (-1.0 到 1.0)
    const normalizedX = (x / canvasWidth) * 2.0 - 1.0
    const normalizedY = -((y / canvasHeight) * 2.0 - 1.0)
    
    // 检查点击区域并播放相应动作
    const hitArea = this.currentModel.hitTest(normalizedX, normalizedY)
    if (hitArea) {
      console.log(`Hit area: ${hitArea}`)
      // 根据点击区域播放不同动作
      if (hitArea === 'Head') {
        this.startMotion('TapHead', 0, 3)
      } else if (hitArea === 'Body') {
        this.startMotion('TapBody', 0, 3)
      }
    }
  }

  /**
   * 调整画布大小
   * @param {number} width - 宽度
   * @param {number} height - 高度
   */
  onResize(width, height) {
    if (!this.canvas) return
    
    this.canvas.width = width
    this.canvas.height = height
    
    if (this.gl) {
      this.gl.viewport(0, 0, width, height)
    }
    
    this.updateViewMatrix()
    console.log(`Canvas resized to: ${width}x${height}`)
  }

  /**
   * 更新视图矩阵
   */
  updateViewMatrix() {
    if (!this.canvas || !this.viewMatrix || !this.deviceToScreen) return
    
    const width = this.canvas.width
    const height = this.canvas.height
    const aspectRatio = width / height
    
    // 设备坐标到屏幕坐标的变换
    this.deviceToScreen.loadIdentity()
    
    // 根据宽高比调整缩放，保持模型比例
    if (aspectRatio > 1.0) {
      // 宽屏：缩放高度
      this.deviceToScreen.scaleRelative(1.0 / aspectRatio, 1.0)
    } else {
      // 高屏：缩放宽度
      this.deviceToScreen.scaleRelative(1.0, aspectRatio)
    }
    
    // 视图矩阵设置 - 修正比例计算
    this.viewMatrix.setScreenRect(-1.0, 1.0, -1.0, 1.0)
    
    // 应用保存的缩放值
    if (this.currentScale) {
      this.viewMatrix.scale(this.currentScale, this.currentScale)
    }
  }

  /**
   * 获取模型信息
   */
  getModelInfo() {
    if (!this.currentModel) {
      return null
    }
    
    return {
      isLoaded: this.isModelLoaded,
      parameterCount: this.currentModel.getParameterCount(),
      partCount: this.currentModel.getPartCount(),
      drawableCount: this.currentModel.getDrawableCount()
    }
  }

  /**
   * 获取模型的HitAreas信息
   * @returns {Array} - HitArea信息数组
   */
  getModelHitAreas() {
    if (!this.isModelLoaded || !this.currentModel) {
      return []
    }
    
    return this.currentModel.getHitAreas()
  }

  /**
   * 测试指定坐标是否命中模型的HitArea
   * @param {number} x - 屏幕X坐标
   * @param {number} y - 屏幕Y坐标
   * @returns {string|null} - 命中的区域名称
   */
  hitTestAtScreenCoordinate(x, y) {
    if (!this.isModelLoaded || !this.currentModel) {
      return null
    }
    
    // 获取canvas的显示尺寸
    const canvasWidth = this.canvas.clientWidth
    const canvasHeight = this.canvas.clientHeight
    
    // 转换坐标到设备坐标空间 (-1.0 到 1.0)
    let deviceX = (x / canvasWidth) * 2.0 - 1.0
    let deviceY = -((y / canvasHeight) * 2.0 - 1.0)
    
    // 应用设备到屏幕的逆变换
    if (this.deviceToScreen) {
      deviceX = this.deviceToScreen.invertTransformX(deviceX)
      deviceY = this.deviceToScreen.invertTransformY(deviceY)
    }
    
    // 应用视图矩阵的逆变换
    if (this.viewMatrix) {
      deviceX = this.viewMatrix.invertTransformX(deviceX)
      deviceY = this.viewMatrix.invertTransformY(deviceY)
    }
    
    return this.currentModel.hitTest(deviceX, deviceY)
  }

  /**
   * 检查是否已加载模型
   */
  isLoaded() {
    return this.isModelLoaded
  }

  /**
   * 释放资源
   */
  release() {
    this.stopRendering()
    
    if (this.currentModel) {
      this.currentModel.release()
      this.currentModel = null
    }
    
    // 释放背景资源
    this.releaseBackground()
    
    // 释放Live2D Framework
    if (this.isInitialized) {
      Live2DCubismFramework.CubismFramework.dispose()
    }
    
    this.isInitialized = false
    this.isModelLoaded = false
    this.gl = null
    this.canvas = null
    
    console.log('Live2D Manager released')
  }

  /**
   * 播放动作
   * @param {string} group - 动作组名
   * @param {number} no - 动作编号
   * @param {number} priority - 优先级
   */
  playMotion(group, no = 0, priority = 3) {
    if (!this.isModelLoaded || !this.currentModel) {
      console.warn('No model loaded')
      return
    }
    
    this.currentModel.startMotion(group, no, priority)
    console.log(`Playing motion: ${group}[${no}] with priority ${priority}`)
  }

  /**
   * 播放随机动作
   * @param {string} group - 动作组名
   * @param {number} priority - 优先级
   */
  playRandomMotion(group, priority = 3) {
    if (!this.isModelLoaded || !this.currentModel) {
      console.warn('No model loaded')
      return
    }
    
    this.currentModel.startRandomMotion(group, priority)
    console.log(`Playing random motion from group: ${group} with priority ${priority}`)
  }

  /**
   * 设置口型同步值
   * @param {number} value - 口型开合值 (0.0 到 1.0)
   */
  setLipSyncValue(value) {
    if (!this.isModelLoaded || !this.currentModel) {
      return
    }
    
    // 限制值在0.0到1.0之间
    const clampedValue = Math.max(0.0, Math.min(1.0, value))
    
    // 设置到模型的口型同步参数
    if (this.currentModel._lipSyncIds && this.currentModel._lipSyncIds.getSize() > 0) {
      // 同时设置到模型实例
      this.currentModel.setLipSyncValue(clampedValue)
      
      for (let i = 0; i < this.currentModel._lipSyncIds.getSize(); ++i) {
        this.currentModel._model.addParameterValueById(
          this.currentModel._lipSyncIds.at(i), 
          clampedValue, 
          0.8
        )
      }
    }
  }

  /**
   * 设置拖拽参数（用于眼神跟随）
   * @param {number} x - X坐标 (-1.0 到 1.0)
   * @param {number} y - Y坐标 (-1.0 到 1.0)
   */
  setDragging(x, y) {
    this._dragManager.set(x, y)
  }

  /**
   * 设置眼神跟随功能
   * @param {boolean} enabled - 是否启用眼神跟随
   */
  setEyeTracking(enabled) {
    this.eyeTrackingEnabled = enabled
    console.log(`Eye tracking ${enabled ? 'enabled' : 'disabled'}`)
    
    // 如果禁用眼神跟随，重置眼球位置到中心
    if (!enabled && this.currentModel) {
      this.currentModel.setDragging(0, 0)
    }
  }

  /**
   * 设置模型缩放
   * @param {number} scale - 缩放比例 (0.1 到 3.0)
   */
  setModelScale(scale) {
    if (!this.viewMatrix) {
      console.warn('View matrix not initialized')
      return
    }
    
    // 限制缩放范围
    const clampedScale = Math.max(0.1, Math.min(3.0, scale))
    
    // 保存当前缩放值
    this.currentScale = clampedScale
    
    // 重置视图矩阵并应用新的缩放
    this.updateViewMatrix()
    
    console.log(`Model scale set to: ${clampedScale}`)
  }

  /**
   * 从路径中提取模型名称
   * @param {string} path - 模型路径
   */
  extractModelName(path) {
    const parts = path.split('/')
    const filename = parts[parts.length - 1]
    return filename.replace('.model3.json', '')
  }

  /**
   * 初始化背景着色器
   */
  initializeBackgroundShader() {
    const gl = this.gl
    if (!gl) return
    
    // 顶点着色器
    const vertexShaderSource = `
      attribute vec2 position;
      attribute vec2 uv;
      varying vec2 vuv;
      void main() {
        gl_Position = vec4(position, 0.0, 1.0);
        vuv = uv;
      }
    `
    
    // 片段着色器
    const fragmentShaderSource = `
      precision mediump float;
      varying vec2 vuv;
      uniform sampler2D texture;
      uniform float opacity;
      void main() {
        vec4 texColor = texture2D(texture, vuv);
        gl_FragColor = vec4(texColor.rgb, texColor.a * opacity);
      }
    `
    
    // 创建着色器程序
    const vertexShader = gl.createShader(gl.VERTEX_SHADER)
    gl.shaderSource(vertexShader, vertexShaderSource)
    gl.compileShader(vertexShader)
    
    const fragmentShader = gl.createShader(gl.FRAGMENT_SHADER)
    gl.shaderSource(fragmentShader, fragmentShaderSource)
    gl.compileShader(fragmentShader)
    
    const shaderProgram = gl.createProgram()
    gl.attachShader(shaderProgram, vertexShader)
    gl.attachShader(shaderProgram, fragmentShader)
    gl.linkProgram(shaderProgram)
    
    this.backgroundShaderProgram = shaderProgram
    
    // 创建顶点缓冲区
    this.backgroundVertexBuffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, this.backgroundVertexBuffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
      -1.0, -1.0,
       1.0, -1.0,
       1.0,  1.0,
      -1.0,  1.0
    ]), gl.STATIC_DRAW)
    
    // 创建UV缓冲区
    this.backgroundUVBuffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, this.backgroundUVBuffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
      0.0, 1.0,
      1.0, 1.0,
      1.0, 0.0,
      0.0, 0.0
    ]), gl.STATIC_DRAW)
    
    // 创建索引缓冲区
    this.backgroundIndexBuffer = gl.createBuffer()
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.backgroundIndexBuffer)
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array([0, 1, 2, 0, 2, 3]), gl.STATIC_DRAW)
  }
  
  /**
   * 加载背景图片
   * @param {File} file - 图片文件
   * @returns {Promise<boolean>} - 是否成功加载
   */
  async loadBackgroundImage(file) {
    if (!this.gl || !this.isInitialized) {
      console.warn('Cannot load background: WebGL not initialized')
      return false
    }
    
    try {
      // 释放之前的背景纹理
      this.releaseBackground()
      
      // 创建图片URL
      const imageUrl = URL.createObjectURL(file)
      
      // 加载图片
      const image = new Image()
      image.src = imageUrl
      
      await new Promise((resolve, reject) => {
        image.onload = resolve
        image.onerror = reject
      })
      
      // 创建纹理
      const gl = this.gl
      const texture = gl.createTexture()
      gl.bindTexture(gl.TEXTURE_2D, texture)
      
      // 设置纹理参数
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
      
      // 上传图片数据到纹理
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image)
      
      // 保存纹理
      this.backgroundTexture = texture
      
      // 释放URL对象
      URL.revokeObjectURL(imageUrl)
      
      console.log('Background image loaded successfully')
      return true
      
    } catch (error) {
      console.error('Failed to load background image:', error)
      return false
    }
  }
  
  /**
   * 绘制背景
   */
  drawBackground() {
    const gl = this.gl
    if (!gl || !this.backgroundTexture || !this.backgroundShaderProgram) return
    
    // 保存当前的混合状态
    const blendEnabled = gl.isEnabled(gl.BLEND)
    
    // 禁用深度测试，启用混合
    gl.disable(gl.DEPTH_TEST)
    gl.enable(gl.BLEND)
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)
    
    // 使用背景着色器程序
    gl.useProgram(this.backgroundShaderProgram)
    
    // 设置顶点属性
    const positionLocation = gl.getAttribLocation(this.backgroundShaderProgram, 'position')
    gl.bindBuffer(gl.ARRAY_BUFFER, this.backgroundVertexBuffer)
    gl.enableVertexAttribArray(positionLocation)
    gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0)
    
    // 设置UV属性
    const uvLocation = gl.getAttribLocation(this.backgroundShaderProgram, 'uv')
    gl.bindBuffer(gl.ARRAY_BUFFER, this.backgroundUVBuffer)
    gl.enableVertexAttribArray(uvLocation)
    gl.vertexAttribPointer(uvLocation, 2, gl.FLOAT, false, 0, 0)
    
    // 设置纹理
    const textureLocation = gl.getUniformLocation(this.backgroundShaderProgram, 'texture')
    gl.activeTexture(gl.TEXTURE0)
    gl.bindTexture(gl.TEXTURE_2D, this.backgroundTexture)
    gl.uniform1i(textureLocation, 0)
    
    // 设置透明度
    const opacityLocation = gl.getUniformLocation(this.backgroundShaderProgram, 'opacity')
    gl.uniform1f(opacityLocation, this.backgroundOpacity)
    
    // 绘制背景
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.backgroundIndexBuffer)
    gl.drawElements(gl.TRIANGLES, 6, gl.UNSIGNED_SHORT, 0)
    
    // 禁用顶点属性
    gl.disableVertexAttribArray(positionLocation)
    gl.disableVertexAttribArray(uvLocation)
    
    // 恢复之前的混合状态
    if (!blendEnabled) {
      gl.disable(gl.BLEND)
    }
  }
  
  /**
   * 释放背景资源
   */
  releaseBackground() {
    const gl = this.gl
    if (!gl) return
    
    // 删除纹理
    if (this.backgroundTexture) {
      gl.deleteTexture(this.backgroundTexture)
      this.backgroundTexture = null
    }
  }
  
  /**
   * 设置背景透明度
   * @param {number} opacity - 透明度值 (0.0 - 1.0)
   */
  setBackgroundOpacity(opacity) {
    this.backgroundOpacity = Math.max(0.0, Math.min(1.0, opacity))
  }
  
  /**
   * 清除背景
   */
  clearBackground() {
    this.releaseBackground()
  }
}

export default Live2DManager